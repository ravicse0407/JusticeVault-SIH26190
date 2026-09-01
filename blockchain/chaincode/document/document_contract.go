/*
 * JUSTICEVAULT - Hyperledger Fabric Smart Contract (Chaincode)
 * Smart India Hackathon 2026 | Problem Statement: SIH26190 | Team: GenX
 * Channel: channel-legal-evidence | Chaincode: evidence_cc
 * Contract: DocumentRegistryContract
 */

package main

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// DocumentContract provides functions for managing legal evidence provenance
type DocumentContract struct {
	contractapi.Contract
}

// DocumentRecord represents the on-chain metadata anchor
type DocumentRecord struct {
	DocumentID        string `json:"documentId"`
	CaseID            string `json:"caseId"`
	DocumentType      string `json:"documentType"`
	CurrentVersion    int    `json:"currentVersion"`
	OriginalHash      string `json:"originalHash"`
	CurrentHash       string `json:"currentHash"`
	Status            string `json:"status"` // INTACT, TAMPERED, SEALED
	CreatedBy         string `json:"createdBy"`
	SubmitterMSP      string `json:"submitterMSP"`
	RegistrationTime  string `json:"registrationTime"`
	LastModifiedTime  string `json:"lastModifiedTime"`
}

// VersionRecord represents an immutable version entry in the provenance tree
type VersionRecord struct {
	VersionID        string `json:"versionId"`
	DocumentID       string `json:"documentId"`
	CaseID           string `json:"caseId"`
	VersionNum       int    `json:"versionNum"`
	FileHash         string `json:"fileHash"`
	ParentHash       string `json:"parentHash"`
	Reason           string `json:"reason"`
	CreatedBy        string `json:"createdBy"`
	Timestamp        string `json:"timestamp"`
}

// InitLedger initializes the ledger
func (c *DocumentContract) InitLedger(ctx contractapi.TransactionContextInterface) error {
	fmt.Println("JusticeVault Document Provenance Ledger Initialized.")
	return nil
}

// RegisterDocument anchors a new document's cryptographic hash on the blockchain
func (c *DocumentContract) RegisterDocument(
	ctx contractapi.TransactionContextInterface,
	documentID string,
	caseID string,
	docType string,
	sha256Hash string,
	createdBy string,
) error {
	exists, err := c.DocumentExists(ctx, documentID)
	if err != nil {
		return err
	}
	if exists {
		return fmt.Errorf("document %s already anchored on ledger", documentID)
	}

	mspID, err := ctx.GetClientIdentity().GetMSPID()
	if err != nil {
		mspID = "PoliceHQ.Org1MSP" // default fallback in simulation
	}

	now := time.Now().UTC().Format(time.RFC3339)
	doc := DocumentRecord{
		DocumentID:       documentID,
		CaseID:           caseID,
		DocumentType:     docType,
		CurrentVersion:   1,
		OriginalHash:     sha256Hash,
		CurrentHash:      sha256Hash,
		Status:           "INTACT",
		CreatedBy:        createdBy,
		SubmitterMSP:     mspID,
		RegistrationTime: now,
		LastModifiedTime: now,
	}

	docJSON, err := json.Marshal(doc)
	if err != nil {
		return err
	}

	// Register initial V1 version anchor
	v1 := VersionRecord{
		VersionID:   fmt.Sprintf("%s-v1", documentID),
		DocumentID:  documentID,
		CaseID:      caseID,
		VersionNum:  1,
		FileHash:    sha256Hash,
		ParentHash:  "0000000000000000000000000000000000000000000000000000000000000000",
		Reason:      "Initial authentic evidence deposition",
		CreatedBy:   createdBy,
		Timestamp:   now,
	}
	v1JSON, _ := json.Marshal(v1)
	_ = ctx.GetStub().PutState(v1.VersionID, v1JSON)

	return ctx.GetStub().PutState(documentID, docJSON)
}

// RegisterDocumentVersion preserves original V1 and registers new V2/V3 version anchor
func (c *DocumentContract) RegisterDocumentVersion(
	ctx contractapi.TransactionContextInterface,
	documentID string,
	newVersionNum int,
	newHash string,
	parentHash string,
	reason string,
	createdBy string,
) error {
	docJSON, err := ctx.GetStub().GetState(documentID)
	if err != nil || docJSON == nil {
		return fmt.Errorf("document %s does not exist on ledger", documentID)
	}

	var doc DocumentRecord
	err = json.Unmarshal(docJSON, &doc)
	if err != nil {
		return err
	}

	now := time.Now().UTC().Format(time.RFC3339)
	versionID := fmt.Sprintf("%s-v%d", documentID, newVersionNum)
	version := VersionRecord{
		VersionID:   versionID,
		DocumentID:  documentID,
		CaseID:      doc.CaseID,
		VersionNum:  newVersionNum,
		FileHash:    newHash,
		ParentHash:  parentHash,
		Reason:      reason,
		CreatedBy:   createdBy,
		Timestamp:   now,
	}

	versionJSON, err := json.Marshal(version)
	if err != nil {
		return err
	}
	err = ctx.GetStub().PutState(versionID, versionJSON)
	if err != nil {
		return err
	}

	doc.CurrentVersion = newVersionNum
	doc.CurrentHash = newHash
	doc.LastModifiedTime = now

	updatedDocJSON, err := json.Marshal(doc)
	if err != nil {
		return err
	}
	return ctx.GetStub().PutState(documentID, updatedDocJSON)
}

// VerifyDocumentProof checks whether a supplied SHA-256 hash matches the on-chain immutable root
func (c *DocumentContract) VerifyDocumentProof(
	ctx contractapi.TransactionContextInterface,
	documentID string,
	suppliedHash string,
) (bool, error) {
	docJSON, err := ctx.GetStub().GetState(documentID)
	if err != nil || docJSON == nil {
		return false, fmt.Errorf("document %s not found on ledger", documentID)
	}

	var doc DocumentRecord
	err = json.Unmarshal(docJSON, &doc)
	if err != nil {
		return false, err
	}

	return doc.CurrentHash == suppliedHash, nil
}

// DocumentExists returns true when document with given ID exists in world state
func (c *DocumentContract) DocumentExists(ctx contractapi.TransactionContextInterface, documentID string) (bool, error) {
	docJSON, err := ctx.GetStub().GetState(documentID)
	if err != nil {
		return false, err
	}
	return docJSON != nil, nil
}

func main() {
	chaincode, err := contractapi.NewChaincode(&DocumentContract{})
	if err != nil {
		fmt.Printf("Error creating JusticeVault document chaincode: %s", err.Error())
		return
	}

	if err := chaincode.Start(); err != nil {
		fmt.Printf("Error starting JusticeVault document chaincode: %s", err.Error())
	}
}
