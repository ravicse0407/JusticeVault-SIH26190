/*
 * JUSTICEVAULT - Hyperledger Fabric Smart Contract (Chaincode)
 * Smart India Hackathon 2026 | Problem Statement: SIH26190 | Team: GenX
 * Channel: channel-legal-evidence | Chaincode: tamper_cc
 * Contract: TamperQuarantineContract
 */

package main

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

type TamperContract struct {
	contractapi.Contract
}

type TamperIncident struct {
	IncidentID          string `json:"incidentId"`
	DocumentID          string `json:"documentId"`
	CaseID              string `json:"caseId"`
	OriginalHash        string `json:"originalHash"`
	DetectedTamperHash  string `json:"detectedTamperHash"`
	Status              string `json:"status"` // QUARANTINED_UNTRUSTED
	ReportedBy          string `json:"reportedBy"`
	Timestamp           string `json:"timestamp"`
	IntegrityVerdict    string `json:"integrityVerdict"`
}

func (c *TamperContract) RecordTamperIncident(
	ctx contractapi.TransactionContextInterface,
	incidentID string,
	documentID string,
	caseID string,
	originalHash string,
	detectedTamperHash string,
	reportedBy string,
) error {
	now := time.Now().UTC().Format(time.RFC3339)

	incident := TamperIncident{
		IncidentID:         incidentID,
		DocumentID:         documentID,
		CaseID:             caseID,
		OriginalHash:       originalHash,
		DetectedTamperHash: detectedTamperHash,
		Status:             "QUARANTINED_UNTRUSTED",
		ReportedBy:         reportedBy,
		Timestamp:          now,
		IntegrityVerdict:   "TAMPER_DETECTED_HASH_MISMATCH",
	}

	incidentJSON, err := json.Marshal(incident)
	if err != nil {
		return err
	}

	return ctx.GetStub().PutState(fmt.Sprintf("TAMPER-%s", incidentID), incidentJSON)
}

func main() {
	chaincode, err := contractapi.NewChaincode(&TamperContract{})
	if err != nil {
		fmt.Printf("Error creating JusticeVault tamper chaincode: %s", err.Error())
		return
	}
	_ = chaincode.Start()
}
