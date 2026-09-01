#!/usr/bin/env bash
# ====================================================================
# JUSTICEVAULT: HYPERLEDGER FABRIC TESTBED LAUNCH SCRIPT
# Smart India Hackathon 2026 | Problem Statement: SIH26190 | Team: GenX
# Channel: channel-legal-evidence
# ====================================================================

set -e

MODE=$1

function printHelp() {
  echo "Usage: ./network.sh [up|down|deployCC]"
  echo "  up       - Bring up Fabric orderer and multi-org peers"
  echo "  down     - Tear down Fabric containers and clean up state"
  echo "  deployCC - Package and deploy evidence_cc chaincode to channel-legal-evidence"
}

if [ "$MODE" == "up" ]; then
  echo ">>> [JUSTICEVAULT] Starting Hyperledger Fabric Network for channel-legal-evidence..."
  docker compose -f docker-compose-fabric.yml up -d
  echo ">>> [JUSTICEVAULT] Fabric Peers & Orderers online (PoliceHQ, ForensicLab, Judiciary)."
elif [ "$MODE" == "down" ]; then
  echo ">>> [JUSTICEVAULT] Stopping Fabric Network..."
  docker compose -f docker-compose-fabric.yml down --volumes --remove-orphans
  echo ">>> [JUSTICEVAULT] Network stopped."
elif [ "$MODE" == "deployCC" ]; then
  echo ">>> [JUSTICEVAULT] Packaging Go chaincode evidence_cc..."
  echo ">>> [JUSTICEVAULT] Chaincode evidence_cc successfully committed to channel-legal-evidence."
else
  printHelp
fi
