/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * vanet-simulation.cc
 * ===================
 *
 * Realistic Urban VANET Safety Communications Simulation
 * Updated for NS-3.42+ (uses integrated WiFi 802.11p support)
 *
 * This simulation implements a comprehensive VANET scenario for studying
 * safety communications using IEEE 802.11p.
 *
 * Features:
 * - Configurable urban grid topology (4-16 intersections)
 * - Variable vehicle density (30, 60, 120 vehicles)
 * - Stop-and-go mobility with traffic light simulation
 * - IEEE 802.11p wireless communication (5.9 GHz)
 * - Safety beacon broadcasting (10 Hz, 200-400 bytes)
 * - Event-driven alerts (hard braking simulation)
 * - Support for AODV and OLSR routing protocols
 * - Comprehensive instrumentation (FlowMonitor, PCAP, custom logging)
 *
 * Usage:
 *   ./ns3 run "vanet-simulation --numVehicles=60 --routingProtocol=AODV"
 *
 * Author: VANET Project Team
 * Course: Data Communications and Computer Networks
 */

#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <cmath>
#include <random>
#include <algorithm>
#include <iomanip>

// NS-3 Core modules
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/applications-module.h"

// Wireless modules (802.11p is now in wifi-module)
#include "ns3/wifi-module.h"
#include "ns3/propagation-module.h"

// Routing protocols
#include "ns3/aodv-module.h"
#include "ns3/olsr-module.h"

// Monitoring and tracing
#include "ns3/flow-monitor-module.h"
#include "ns3/stats-module.h"

// Animation
#include "ns3/netanim-module.h"

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("VanetSimulation");

// ============================================================================
// GLOBAL CONFIGURATION
// ============================================================================

struct SimulationConfig {
    // Topology
    uint32_t gridSizeX = 4;
    uint32_t gridSizeY = 4;
    double blockSize = 200.0;

    // Vehicles
    uint32_t numVehicles = 60;
    double vehicleSpeed = 13.89;  // m/s (50 km/h)
    double speedVariation = 0.2;

    // Traffic lights
    bool enableTrafficLights = true;
    double stopDuration = 5.0;

    // Wireless (802.11p)
    double txPowerDbm = 20.0;
    double frequency = 5.9e9;
    std::string dataRate = "OfdmRate6MbpsBW10MHz";
    double ccaThreshold = -85.0;

    // Application
    double beaconInterval = 0.1;  // 10 Hz
    uint32_t beaconSize = 300;
    uint32_t alertSize = 600;
    double alertProbability = 0.001;

    // Simulation
    double simTime = 300.0;
    double warmupTime = 30.0;
    std::string routingProtocol = "AODV";
    uint32_t randomSeed = 1;

    // Output
    std::string outputDir = "./results";
    std::string experimentName = "vanet";
    bool enablePcap = true;
    bool enableFlowMonitor = true;
    bool enableCustomLogging = true;
    bool enableNetAnim = false;
    bool verbose = false;
};

SimulationConfig g_config;

// Statistics
struct SimulationStats {
    uint64_t totalBeaconsSent = 0;
    uint64_t totalBeaconsReceived = 0;
    uint64_t totalAlertsSent = 0;
    uint64_t totalAlertsReceived = 0;
    uint64_t totalBytesSent = 0;
    uint64_t totalBytesReceived = 0;
    std::vector<double> e2eDelays;
    std::vector<double> alertDelays;
};

SimulationStats g_stats;

// Output streams
std::ofstream g_packetLog;
std::ofstream g_mobilityLog;

// ============================================================================
// VANET BEACON APPLICATION
// ============================================================================

class VanetBeaconApplication : public Application
{
public:
    static TypeId GetTypeId(void);
    VanetBeaconApplication();
    virtual ~VanetBeaconApplication();

    void Setup(Ipv4Address broadcastAddr, uint16_t port,
               uint32_t packetSize, double interval);

protected:
    virtual void StartApplication(void);
    virtual void StopApplication(void);

private:
    void SendBeacon(void);
    void ScheduleNextBeacon(void);

    Ptr<Socket> m_socket;
    Ipv4Address m_broadcastAddr;
    uint16_t m_port;
    uint32_t m_packetSize;
    double m_interval;
    EventId m_sendEvent;
    bool m_running;
    uint32_t m_sequenceNumber;
    Ptr<UniformRandomVariable> m_rng;
};

NS_OBJECT_ENSURE_REGISTERED(VanetBeaconApplication);

TypeId VanetBeaconApplication::GetTypeId(void)
{
    static TypeId tid = TypeId("ns3::VanetBeaconApplication")
        .SetParent<Application>()
        .SetGroupName("Applications")
        .AddConstructor<VanetBeaconApplication>();
    return tid;
}

VanetBeaconApplication::VanetBeaconApplication()
    : m_socket(0), m_port(0), m_packetSize(300), m_interval(0.1),
      m_running(false), m_sequenceNumber(0)
{
    m_rng = CreateObject<UniformRandomVariable>();
}

VanetBeaconApplication::~VanetBeaconApplication()
{
    m_socket = 0;
}

void VanetBeaconApplication::Setup(Ipv4Address broadcastAddr, uint16_t port,
                                    uint32_t packetSize, double interval)
{
    m_broadcastAddr = broadcastAddr;
    m_port = port;
    m_packetSize = packetSize;
    m_interval = interval;
}

void VanetBeaconApplication::StartApplication(void)
{
    m_running = true;
    m_sequenceNumber = 0;

    if (!m_socket)
    {
        TypeId tid = TypeId::LookupByName("ns3::UdpSocketFactory");
        m_socket = Socket::CreateSocket(GetNode(), tid);
        m_socket->SetAllowBroadcast(true);
        // Don't bind to the destination port - use ephemeral port for sending
        // The receiver will listen on m_port
    }

    double jitter = m_rng->GetValue(0.0, m_interval);
    m_sendEvent = Simulator::Schedule(Seconds(jitter), &VanetBeaconApplication::SendBeacon, this);
}

void VanetBeaconApplication::StopApplication(void)
{
    m_running = false;
    if (m_sendEvent.IsPending())
        Simulator::Cancel(m_sendEvent);
    if (m_socket)
        m_socket->Close();
}

void VanetBeaconApplication::SendBeacon(void)
{
    if (!m_running) return;

    bool isAlert = (m_rng->GetValue() < g_config.alertProbability);
    uint32_t size = isAlert ? g_config.alertSize : m_packetSize;

    uint8_t packetType = isAlert ? 1 : 0;
    uint32_t nodeId = GetNode()->GetId();
    double timestamp = Simulator::Now().GetSeconds();

    std::ostringstream headerStream;
    headerStream << std::setfill('0')
                 << std::setw(1) << (int)packetType
                 << std::setw(8) << m_sequenceNumber
                 << std::setw(12) << std::fixed << std::setprecision(6) << timestamp
                 << std::setw(4) << nodeId;

    std::string header = headerStream.str();
    uint32_t headerSize = std::min((uint32_t)header.size(), size);
    uint32_t paddingSize = size - headerSize;

    Ptr<Packet> packet = Create<Packet>((const uint8_t*)header.c_str(), headerSize);
    if (paddingSize > 0)
    {
        Ptr<Packet> padding = Create<Packet>(paddingSize);
        packet->AddAtEnd(padding);
    }

    InetSocketAddress remote = InetSocketAddress(m_broadcastAddr, m_port);
    m_socket->SendTo(packet, 0, remote);

    if (isAlert)
        g_stats.totalAlertsSent++;
    else
        g_stats.totalBeaconsSent++;
    g_stats.totalBytesSent += size;

    if (g_config.enableCustomLogging && g_packetLog.is_open())
    {
        g_packetLog << std::fixed << std::setprecision(6)
                    << Simulator::Now().GetSeconds() << ","
                    << nodeId << ",TX,"
                    << (isAlert ? "ALERT" : "BEACON") << ","
                    << m_sequenceNumber << "," << size << ",-1"
                    << std::endl;
    }

    m_sequenceNumber++;
    ScheduleNextBeacon();
}

void VanetBeaconApplication::ScheduleNextBeacon(void)
{
    if (m_running)
    {
        double jitter = m_rng->GetValue(-0.01, 0.01) * m_interval;
        m_sendEvent = Simulator::Schedule(Seconds(m_interval + jitter),
                                           &VanetBeaconApplication::SendBeacon, this);
    }
}

// ============================================================================
// VANET RECEIVER APPLICATION
// ============================================================================

class VanetReceiverApplication : public Application
{
public:
    static TypeId GetTypeId(void);
    VanetReceiverApplication();
    virtual ~VanetReceiverApplication();

    void Setup(uint16_t port);

protected:
    virtual void StartApplication(void);
    virtual void StopApplication(void);

private:
    void HandleRead(Ptr<Socket> socket);

    Ptr<Socket> m_socket;
    uint16_t m_port;
};

NS_OBJECT_ENSURE_REGISTERED(VanetReceiverApplication);

TypeId VanetReceiverApplication::GetTypeId(void)
{
    static TypeId tid = TypeId("ns3::VanetReceiverApplication")
        .SetParent<Application>()
        .SetGroupName("Applications")
        .AddConstructor<VanetReceiverApplication>();
    return tid;
}

VanetReceiverApplication::VanetReceiverApplication() : m_socket(0), m_port(0) {}
VanetReceiverApplication::~VanetReceiverApplication() { m_socket = 0; }

void VanetReceiverApplication::Setup(uint16_t port) { m_port = port; }

void VanetReceiverApplication::StartApplication(void)
{
    if (!m_socket)
    {
        TypeId tid = TypeId::LookupByName("ns3::UdpSocketFactory");
        m_socket = Socket::CreateSocket(GetNode(), tid);
        m_socket->SetAllowBroadcast(true);  // Allow receiving broadcast packets
        InetSocketAddress local = InetSocketAddress(Ipv4Address::GetAny(), m_port);
        if (m_socket->Bind(local) == -1)
        {
            NS_LOG_ERROR("Failed to bind socket on node " << GetNode()->GetId());
        }
        m_socket->SetRecvCallback(MakeCallback(&VanetReceiverApplication::HandleRead, this));
        NS_LOG_DEBUG("Receiver socket bound on node " << GetNode()->GetId() << " port " << m_port);
    }
}

void VanetReceiverApplication::StopApplication(void)
{
    if (m_socket)
        m_socket->Close();
}

void VanetReceiverApplication::HandleRead(Ptr<Socket> socket)
{
    Ptr<Packet> packet;
    Address from;

    while ((packet = socket->RecvFrom(from)))
    {
        double rxTime = Simulator::Now().GetSeconds();
        uint32_t receiverId = GetNode()->GetId();
        uint32_t packetSize = packet->GetSize();

        uint8_t buffer[64];
        uint32_t copySize = std::min((uint32_t)64, packetSize);
        packet->CopyData(buffer, copySize);

        std::string header((char*)buffer, copySize);

        bool isAlert = (header.length() > 0 && header[0] == '1');

        double txTime = 0.0;
        uint32_t senderId = 0;
        uint32_t seqNum = 0;

        // Header format: 1 (type) + 8 (seq) + 12 (time) + 4 (nodeId) = 25 chars
        if (header.length() >= 25)
        {
            try {
                seqNum = std::stoul(header.substr(1, 8));
                txTime = std::stod(header.substr(9, 12));
                senderId = std::stoul(header.substr(21, 4));
            } catch (...) {
                continue;
            }
        }
        else
        {
            continue;  // Skip malformed packets
        }

        if (senderId == receiverId) continue;

        double delay = rxTime - txTime;
        if (delay < 0 || delay > 10.0) continue;

        if (isAlert)
        {
            g_stats.totalAlertsReceived++;
            g_stats.alertDelays.push_back(delay);
        }
        else
        {
            g_stats.totalBeaconsReceived++;
            g_stats.e2eDelays.push_back(delay);
        }
        g_stats.totalBytesReceived += packetSize;

        if (g_config.enableCustomLogging && g_packetLog.is_open())
        {
            g_packetLog << std::fixed << std::setprecision(6)
                        << rxTime << "," << receiverId << ",RX,"
                        << (isAlert ? "ALERT" : "BEACON") << ","
                        << seqNum << "," << packetSize << ","
                        << senderId << "," << (delay * 1000.0)
                        << std::endl;
        }
    }
}

// ============================================================================
// MOBILITY CONFIGURATION
// ============================================================================

// Generate waypoints along Manhattan grid streets
void AssignManhattanMobility(Ptr<Node> node, uint32_t nodeId, double simTime)
{
    Ptr<WaypointMobilityModel> waypointMob = node->GetObject<WaypointMobilityModel>();
    if (!waypointMob) return;

    Ptr<UniformRandomVariable> rng = CreateObject<UniformRandomVariable>();
    rng->SetAttribute("Min", DoubleValue(0.0));
    rng->SetAttribute("Max", DoubleValue(1.0));

    // Street positions (at block boundaries)
    std::vector<double> streetX, streetY;
    for (uint32_t i = 0; i <= g_config.gridSizeX; i++) {
        streetX.push_back(i * g_config.blockSize);
    }
    for (uint32_t i = 0; i <= g_config.gridSizeY; i++) {
        streetY.push_back(i * g_config.blockSize);
    }

    // Start on a random street intersection
    double currentX = streetX[rng->GetInteger(0, streetX.size() - 1)];
    double currentY = streetY[rng->GetInteger(0, streetY.size() - 1)];

    // Initial position
    double currentTime = 0.0;
    waypointMob->AddWaypoint(Waypoint(Seconds(currentTime), Vector(currentX, currentY, 0.0)));

    // Generate waypoints along streets
    while (currentTime < simTime) {
        // Choose direction: 0=North, 1=East, 2=South, 3=West
        int direction = rng->GetInteger(0, 3);

        double nextX = currentX;
        double nextY = currentY;
        double distance = g_config.blockSize;

        switch (direction) {
            case 0: // North
                nextY = std::min(currentY + g_config.blockSize, streetY.back());
                break;
            case 1: // East
                nextX = std::min(currentX + g_config.blockSize, streetX.back());
                break;
            case 2: // South
                nextY = std::max(currentY - g_config.blockSize, streetY.front());
                break;
            case 3: // West
                nextX = std::max(currentX - g_config.blockSize, streetX.front());
                break;
        }

        // Skip if no movement (at boundary)
        if (nextX == currentX && nextY == currentY) continue;

        distance = std::sqrt(std::pow(nextX - currentX, 2) + std::pow(nextY - currentY, 2));

        // Calculate travel time with some speed variation
        double speed = g_config.vehicleSpeed * (0.8 + 0.4 * rng->GetValue());
        double travelTime = distance / speed;

        currentTime += travelTime;

        // Add waypoint
        waypointMob->AddWaypoint(Waypoint(Seconds(currentTime), Vector(nextX, nextY, 0.0)));

        // Random pause at intersection (traffic light simulation)
        if (rng->GetValue() < 0.3 && g_config.enableTrafficLights) {
            double pauseTime = g_config.stopDuration * rng->GetValue();
            currentTime += pauseTime;
            waypointMob->AddWaypoint(Waypoint(Seconds(currentTime), Vector(nextX, nextY, 0.0)));
        }

        currentX = nextX;
        currentY = nextY;
    }
}

void ConfigureMobility(NodeContainer& vehicles)
{
    MobilityHelper mobility;

    // Use WaypointMobilityModel for Manhattan grid movement
    mobility.SetMobilityModel("ns3::WaypointMobilityModel");

    // Initial position allocator (will be overwritten by waypoints)
    mobility.SetPositionAllocator("ns3::RandomRectanglePositionAllocator",
        "X", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=" +
                         std::to_string(g_config.gridSizeX * g_config.blockSize) + "]"),
        "Y", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=" +
                         std::to_string(g_config.gridSizeY * g_config.blockSize) + "]"));

    mobility.Install(vehicles);

    // Assign Manhattan grid waypoints to each vehicle
    for (uint32_t i = 0; i < vehicles.GetN(); i++) {
        AssignManhattanMobility(vehicles.Get(i), i, g_config.simTime);
    }

    NS_LOG_INFO("Mobility configured for " << vehicles.GetN() << " vehicles (Manhattan grid)");
}

void LogMobilityState(NodeContainer& vehicles, double interval)
{
    if (!g_config.enableCustomLogging || !g_mobilityLog.is_open()) return;

    double now = Simulator::Now().GetSeconds();

    for (uint32_t i = 0; i < vehicles.GetN(); ++i)
    {
        Ptr<MobilityModel> mob = vehicles.Get(i)->GetObject<MobilityModel>();
        if (mob)
        {
            Vector pos = mob->GetPosition();
            Vector vel = mob->GetVelocity();
            double speed = std::sqrt(vel.x * vel.x + vel.y * vel.y);

            g_mobilityLog << std::fixed << std::setprecision(3)
                          << now << "," << i << ","
                          << pos.x << "," << pos.y << "," << pos.z << ","
                          << vel.x << "," << vel.y << "," << speed
                          << std::endl;
        }
    }

    if (Simulator::Now().GetSeconds() + interval < g_config.simTime)
    {
        Simulator::Schedule(Seconds(interval), &LogMobilityState, vehicles, interval);
    }
}

// ============================================================================
// WIRELESS CONFIGURATION (802.11p via modern WiFi module)
// ============================================================================

NetDeviceContainer ConfigureWifiDevices(NodeContainer& vehicles, YansWifiPhyHelper& wifiPhy)
{
    // Configure channel with propagation models
    YansWifiChannelHelper channel = YansWifiChannelHelper::Default();
    channel.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel");
    channel.AddPropagationLoss("ns3::TwoRayGroundPropagationLossModel",
                               "Frequency", DoubleValue(g_config.frequency),
                               "HeightAboveZ", DoubleValue(1.5));

    wifiPhy.SetChannel(channel.Create());
    wifiPhy.Set("TxPowerStart", DoubleValue(g_config.txPowerDbm));
    wifiPhy.Set("TxPowerEnd", DoubleValue(g_config.txPowerDbm));
    wifiPhy.Set("CcaEdThreshold", DoubleValue(g_config.ccaThreshold));
    wifiPhy.SetPcapDataLinkType(WifiPhyHelper::DLT_IEEE802_11);

    // Configure 802.11p (WAVE)
    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211p);
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                  "DataMode", StringValue(g_config.dataRate),
                                  "ControlMode", StringValue(g_config.dataRate),
                                  "NonUnicastMode", StringValue(g_config.dataRate));

    // Use Adhoc MAC for V2V communication
    WifiMacHelper mac;
    mac.SetType("ns3::AdhocWifiMac");

    NetDeviceContainer devices = wifi.Install(wifiPhy, mac, vehicles);

    NS_LOG_INFO("802.11p devices configured:");
    NS_LOG_INFO("  Tx Power: " << g_config.txPowerDbm << " dBm");
    NS_LOG_INFO("  Data Rate: " << g_config.dataRate);

    return devices;
}

// ============================================================================
// ROUTING PROTOCOL CONFIGURATION
// ============================================================================

void ConfigureRoutingProtocol(NodeContainer& vehicles)
{
    InternetStackHelper internet;

    if (g_config.routingProtocol == "AODV")
    {
        AodvHelper aodv;
        aodv.Set("HelloInterval", TimeValue(Seconds(1.0)));
        aodv.Set("ActiveRouteTimeout", TimeValue(Seconds(3.0)));
        aodv.Set("EnableBroadcast", BooleanValue(true));
        internet.SetRoutingHelper(aodv);
        NS_LOG_INFO("Routing protocol: AODV");
    }
    else if (g_config.routingProtocol == "OLSR")
    {
        OlsrHelper olsr;
        olsr.Set("HelloInterval", TimeValue(Seconds(1.0)));
        olsr.Set("TcInterval", TimeValue(Seconds(2.0)));
        internet.SetRoutingHelper(olsr);
        NS_LOG_INFO("Routing protocol: OLSR");
    }
    else
    {
        NS_LOG_WARN("Unknown routing protocol: " << g_config.routingProtocol);
    }

    internet.Install(vehicles);
}

// ============================================================================
// APPLICATION CONFIGURATION
// ============================================================================

void ConfigureApplications(NodeContainer& vehicles, Ipv4InterfaceContainer& interfaces)
{
    uint16_t beaconPort = 9999;
    Ipv4Address broadcastAddr("255.255.255.255");  // Limited broadcast for wireless

    for (uint32_t i = 0; i < vehicles.GetN(); ++i)
    {
        Ptr<VanetBeaconApplication> beaconApp = CreateObject<VanetBeaconApplication>();
        beaconApp->Setup(broadcastAddr, beaconPort, g_config.beaconSize, g_config.beaconInterval);
        vehicles.Get(i)->AddApplication(beaconApp);
        beaconApp->SetStartTime(Seconds(g_config.warmupTime));
        beaconApp->SetStopTime(Seconds(g_config.simTime - 1.0));

        Ptr<VanetReceiverApplication> recvApp = CreateObject<VanetReceiverApplication>();
        recvApp->Setup(beaconPort);
        vehicles.Get(i)->AddApplication(recvApp);
        recvApp->SetStartTime(Seconds(g_config.warmupTime));
        recvApp->SetStopTime(Seconds(g_config.simTime));
    }

    NS_LOG_INFO("Applications configured: " << vehicles.GetN() << " nodes");
}

// ============================================================================
// STATISTICS OUTPUT
// ============================================================================

void OpenOutputFiles()
{
    std::string mkdirCmd = "mkdir -p " + g_config.outputDir;
    system(mkdirCmd.c_str());

    std::string prefix = g_config.outputDir + "/" + g_config.experimentName;

    if (g_config.enableCustomLogging)
    {
        g_packetLog.open(prefix + "_packets.csv");
        g_packetLog << "time,nodeId,direction,type,seqNum,size,peerId,delayMs" << std::endl;

        g_mobilityLog.open(prefix + "_mobility.csv");
        g_mobilityLog << "time,nodeId,posX,posY,posZ,velX,velY,speed" << std::endl;
    }
}

void CloseOutputFiles()
{
    if (g_packetLog.is_open()) g_packetLog.close();
    if (g_mobilityLog.is_open()) g_mobilityLog.close();
}

double CalculatePercentile(std::vector<double>& data, double percentile)
{
    if (data.empty()) return 0.0;
    std::sort(data.begin(), data.end());
    size_t index = static_cast<size_t>(percentile / 100.0 * (data.size() - 1));
    return data[index];
}

double CalculateMean(const std::vector<double>& data)
{
    if (data.empty()) return 0.0;
    double sum = 0.0;
    for (double val : data) sum += val;
    return sum / data.size();
}

void PrintStatistics(Ptr<FlowMonitor> flowMonitor)
{
    std::string prefix = g_config.outputDir + "/" + g_config.experimentName;
    std::ofstream statsFile(prefix + "_statistics.txt");

    statsFile << "========================================" << std::endl;
    statsFile << "VANET Simulation Results" << std::endl;
    statsFile << "========================================" << std::endl;
    statsFile << std::endl;

    statsFile << "Configuration:" << std::endl;
    statsFile << "  Vehicles: " << g_config.numVehicles << std::endl;
    statsFile << "  Speed: " << g_config.vehicleSpeed * 3.6 << " km/h" << std::endl;
    statsFile << "  Routing: " << g_config.routingProtocol << std::endl;
    statsFile << "  Sim Time: " << g_config.simTime << " s" << std::endl;
    statsFile << std::endl;

    statsFile << "Packet Statistics:" << std::endl;
    statsFile << "  Beacons Sent: " << g_stats.totalBeaconsSent << std::endl;
    statsFile << "  Beacons Received: " << g_stats.totalBeaconsReceived << std::endl;
    statsFile << "  Alerts Sent: " << g_stats.totalAlertsSent << std::endl;
    statsFile << "  Alerts Received: " << g_stats.totalAlertsReceived << std::endl;
    statsFile << std::endl;

    double beaconPdr = 0.0;
    if (g_stats.totalBeaconsSent > 0)
    {
        uint64_t expectedRx = g_stats.totalBeaconsSent * (g_config.numVehicles - 1);
        beaconPdr = (double)g_stats.totalBeaconsReceived / expectedRx * 100.0;
        if (beaconPdr > 100.0) beaconPdr = 100.0;
    }

    statsFile << "PDR: " << std::fixed << std::setprecision(2) << beaconPdr << "%" << std::endl;

    if (!g_stats.e2eDelays.empty())
    {
        double meanDelay = CalculateMean(g_stats.e2eDelays);
        double p50Delay = CalculatePercentile(g_stats.e2eDelays, 50.0);
        double p95Delay = CalculatePercentile(g_stats.e2eDelays, 95.0);
        double p99Delay = CalculatePercentile(g_stats.e2eDelays, 99.0);

        statsFile << std::endl << "Beacon Delay (ms):" << std::endl;
        statsFile << "  Mean: " << meanDelay * 1000.0 << std::endl;
        statsFile << "  P50: " << p50Delay * 1000.0 << std::endl;
        statsFile << "  P95: " << p95Delay * 1000.0 << std::endl;
        statsFile << "  P99: " << p99Delay * 1000.0 << std::endl;
    }

    double effectiveTime = g_config.simTime - g_config.warmupTime;
    double throughputKbps = (g_stats.totalBytesReceived * 8.0) / (effectiveTime * 1000.0);

    statsFile << std::endl << "Throughput: " << throughputKbps << " kbps" << std::endl;
    statsFile << "========================================" << std::endl;
    statsFile.close();

    // Save CSV summary
    std::ofstream csvFile(prefix + "_summary.csv");
    csvFile << "metric,value" << std::endl;
    csvFile << "numVehicles," << g_config.numVehicles << std::endl;
    csvFile << "speedKmh," << g_config.vehicleSpeed * 3.6 << std::endl;
    csvFile << "routingProtocol," << g_config.routingProtocol << std::endl;
    csvFile << "simTime," << g_config.simTime << std::endl;
    csvFile << "randomSeed," << g_config.randomSeed << std::endl;
    csvFile << "beaconsSent," << g_stats.totalBeaconsSent << std::endl;
    csvFile << "beaconsReceived," << g_stats.totalBeaconsReceived << std::endl;
    csvFile << "alertsSent," << g_stats.totalAlertsSent << std::endl;
    csvFile << "alertsReceived," << g_stats.totalAlertsReceived << std::endl;
    csvFile << "pdr," << beaconPdr << std::endl;

    if (!g_stats.e2eDelays.empty())
    {
        csvFile << "delayMean," << CalculateMean(g_stats.e2eDelays) * 1000.0 << std::endl;
        csvFile << "delayP50," << CalculatePercentile(g_stats.e2eDelays, 50.0) * 1000.0 << std::endl;
        csvFile << "delayP95," << CalculatePercentile(g_stats.e2eDelays, 95.0) * 1000.0 << std::endl;
        csvFile << "delayP99," << CalculatePercentile(g_stats.e2eDelays, 99.0) * 1000.0 << std::endl;
    }
    csvFile << "throughputKbps," << throughputKbps << std::endl;
    csvFile.close();

    if (flowMonitor)
    {
        flowMonitor->CheckForLostPackets();
        flowMonitor->SerializeToXmlFile(prefix + "_flowmonitor.xml", true, true);
    }

    // Console output
    std::cout << std::endl;
    std::cout << "========================================" << std::endl;
    std::cout << "Simulation Complete" << std::endl;
    std::cout << "========================================" << std::endl;
    std::cout << "Vehicles: " << g_config.numVehicles << std::endl;
    std::cout << "Routing: " << g_config.routingProtocol << std::endl;
    std::cout << "Beacons: " << g_stats.totalBeaconsSent << " sent, "
              << g_stats.totalBeaconsReceived << " received" << std::endl;

    if (!g_stats.e2eDelays.empty())
    {
        std::cout << "Delay: mean=" << std::fixed << std::setprecision(2)
                  << CalculateMean(g_stats.e2eDelays) * 1000.0 << "ms, p95="
                  << CalculatePercentile(g_stats.e2eDelays, 95.0) * 1000.0 << "ms" << std::endl;
    }
    std::cout << "PDR: " << std::fixed << std::setprecision(1) << beaconPdr << "%" << std::endl;
    std::cout << "Results: " << g_config.outputDir << std::endl;
    std::cout << "========================================" << std::endl;
}

// ============================================================================
// MAIN
// ============================================================================

int main(int argc, char *argv[])
{
    CommandLine cmd;

    cmd.AddValue("gridSizeX", "Grid size X", g_config.gridSizeX);
    cmd.AddValue("gridSizeY", "Grid size Y", g_config.gridSizeY);
    cmd.AddValue("blockSize", "Block size (m)", g_config.blockSize);
    cmd.AddValue("numVehicles", "Number of vehicles", g_config.numVehicles);
    cmd.AddValue("vehicleSpeed", "Vehicle speed (m/s)", g_config.vehicleSpeed);
    cmd.AddValue("txPower", "Tx power (dBm)", g_config.txPowerDbm);
    cmd.AddValue("dataRate", "802.11p data rate", g_config.dataRate);
    cmd.AddValue("beaconInterval", "Beacon interval (s)", g_config.beaconInterval);
    cmd.AddValue("beaconSize", "Beacon size (bytes)", g_config.beaconSize);
    cmd.AddValue("simTime", "Simulation time (s)", g_config.simTime);
    cmd.AddValue("warmupTime", "Warmup time (s)", g_config.warmupTime);
    cmd.AddValue("routingProtocol", "Routing protocol (AODV/OLSR)", g_config.routingProtocol);
    cmd.AddValue("randomSeed", "Random seed", g_config.randomSeed);
    cmd.AddValue("outputDir", "Output directory", g_config.outputDir);
    cmd.AddValue("experimentName", "Experiment name", g_config.experimentName);
    cmd.AddValue("enablePcap", "Enable PCAP", g_config.enablePcap);
    cmd.AddValue("enableFlowMonitor", "Enable FlowMonitor", g_config.enableFlowMonitor);
    cmd.AddValue("enableNetAnim", "Enable NetAnim trace file", g_config.enableNetAnim);
    cmd.AddValue("verbose", "Verbose output", g_config.verbose);

    cmd.Parse(argc, argv);

    RngSeedManager::SetSeed(g_config.randomSeed);
    RngSeedManager::SetRun(g_config.randomSeed);

    if (g_config.verbose)
        LogComponentEnable("VanetSimulation", LOG_LEVEL_ALL);
    else
        LogComponentEnable("VanetSimulation", LOG_LEVEL_INFO);

    NS_LOG_INFO("=== VANET Safety Communications Simulation ===");
    NS_LOG_INFO("Vehicles: " << g_config.numVehicles);
    NS_LOG_INFO("Speed: " << g_config.vehicleSpeed * 3.6 << " km/h");
    NS_LOG_INFO("Routing: " << g_config.routingProtocol);

    OpenOutputFiles();

    // Create nodes
    NodeContainer vehicles;
    vehicles.Create(g_config.numVehicles);

    // Configure mobility
    ConfigureMobility(vehicles);

    // Configure 802.11p
    YansWifiPhyHelper wifiPhy;
    NetDeviceContainer devices = ConfigureWifiDevices(vehicles, wifiPhy);

    // Enable PCAP
    if (g_config.enablePcap)
    {
        std::string pcapPrefix = g_config.outputDir + "/" + g_config.experimentName;
        wifiPhy.EnablePcap(pcapPrefix, devices);
    }

    // Configure routing and install internet stack
    ConfigureRoutingProtocol(vehicles);

    // Assign IP addresses
    Ipv4AddressHelper ipv4;
    ipv4.SetBase("10.1.0.0", "255.255.0.0");
    Ipv4InterfaceContainer interfaces = ipv4.Assign(devices);

    // Configure applications
    ConfigureApplications(vehicles, interfaces);

    // Configure FlowMonitor
    Ptr<FlowMonitor> flowMonitor = nullptr;
    FlowMonitorHelper flowHelper;
    if (g_config.enableFlowMonitor)
    {
        // Install on vehicles only, not globally (InstallAll can cause issues with broadcast)
        flowMonitor = flowHelper.Install(vehicles);
    }

    // Schedule mobility logging
    if (g_config.enableCustomLogging)
    {
        Simulator::Schedule(Seconds(g_config.warmupTime), &LogMobilityState, vehicles, 1.0);
    }

    // Configure NetAnim animation trace
    AnimationInterface* anim = nullptr;
    if (g_config.enableNetAnim)
    {
        std::string animFile = g_config.outputDir + "/" + g_config.experimentName + "_animation.xml";
        anim = new AnimationInterface(animFile);

        // Set node descriptions for better visualization
        for (uint32_t i = 0; i < vehicles.GetN(); i++)
        {
            std::ostringstream desc;
            desc << "V" << i;
            anim->UpdateNodeDescription(vehicles.Get(i), desc.str());
            anim->UpdateNodeColor(vehicles.Get(i), 0, 128, 255);  // Blue vehicles
            anim->UpdateNodeSize(i, 10, 10);  // Larger nodes for visibility
        }

        // Enable packet metadata for detailed packet visualization
        anim->EnablePacketMetadata(true);
        anim->EnableIpv4L3ProtocolCounters(Seconds(0), Seconds(g_config.simTime));

        NS_LOG_INFO("NetAnim trace file: " << animFile);
    }

    // Run simulation
    NS_LOG_INFO("Starting simulation...");
    Simulator::Stop(Seconds(g_config.simTime));
    Simulator::Run();

    PrintStatistics(flowMonitor);

    Simulator::Destroy();
    CloseOutputFiles();

    // Clean up NetAnim
    if (anim)
    {
        delete anim;
    }

    NS_LOG_INFO("Simulation complete.");

    return 0;
}
