from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import TCLink


PROJECT = "/home/vboxuser/remote system health monitoring"
PYTHON = "/usr/bin/python3"


def run():
    net = Mininet(
        switch=OVSBridge,
        link=TCLink
    )

    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")

    s1 = net.addSwitch("s1")

    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(h3, s1)

    net.start()

    print()
    print("==============================================")
    print("   REMOTE SYSTEM HEALTH MONITOR - MININET")
    print("==============================================")
    print("h1  SERVER    10.0.0.1")
    print("h2  NODE-02   10.0.0.2")
    print("h3  NODE-03   10.0.0.3")
    print("==============================================")
    print()
    print("Start the original programs from the Mininet CLI:")
    print()
    print("  h1 python3 server/monitor_server.py --host 10.0.0.1")
    print("  h2 python3 agents/health_agent.py --node-id NODE-02 --host 10.0.0.1 --port 5000")
    print("  h3 python3 agents/health_agent.py --node-id NODE-03 --host 10.0.0.1 --port 5000")
    print()

    CLI(net)

    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
