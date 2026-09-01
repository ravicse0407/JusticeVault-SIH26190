/*
 * JUSTICEVAULT - Hyperledger Fabric Smart Contract (Chaincode)
 * Smart India Hackathon 2026 | Problem Statement: SIH26190 | Team: GenX
 * Channel: channel-legal-evidence | Chaincode: audit_cc
 * Contract: AuditChronicleContract
 */

package main

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

type AuditContract struct {
	contractapi.Contract
}

type AuditEvent struct {
	EventID        string `json:"eventId"`
	UserID         string `json:"userId"`
	Role           string `json:"role"`
	Department     string `json:"department"`
	CaseID         string `json:"caseId"`
	DocumentID     string `json:"documentId"`
	Action         string `json:"action"` // UPLOAD, VIEW, EDIT, UNMASK, E_SIGN, TAMPER_ALERT
	Result         string `json:"result"` // SUCCESS, DENIED, TAMPER_TRIGGERED
	Reason         string `json:"reason"`
	SignatureProof string `json:"signatureProof"`
	Timestamp      string `json:"timestamp"`
	MSPIdentity    string `json:"mspIdentity"`
}

func (c *AuditContract) RecordAuditEvent(
	ctx contractapi.TransactionContextInterface,
	eventID string,
	userID string,
	role string,
	dept string,
	caseID string,
	docID string,
	action string,
	result string,
	reason string,
	sigProof string,
) error {
	mspID, _ := ctx.GetClientIdentity().GetMSPID()
	now := time.Now().UTC().Format(time.RFC3339)

	event := AuditEvent{
		EventID:        eventID,
		UserID:         userID,
		Role:           role,
		Department:     dept,
		CaseID:         caseID,
		DocumentID:     docID,
		Action:         action,
		Result:         result,
		Reason:         reason,
		SignatureProof: sigProof,
		Timestamp:      now,
		MSPIdentity:    mspID,
	}

	eventJSON, err := json.Marshal(event)
	if err != nil {
		return err
	}

	return ctx.GetStub().PutState(fmt.Sprintf("AUDIT-%s", eventID), eventJSON)
}

func main() {
	chaincode, err := contractapi.NewChaincode(&AuditContract{})
	if err != nil {
		fmt.Printf("Error creating JusticeVault audit chaincode: %s", err.Error())
		return
	}
	_ = chaincode.Start()
}
