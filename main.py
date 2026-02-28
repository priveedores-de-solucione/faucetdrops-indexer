from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from web3 import Web3
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from collections import defaultdict
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio, os, requests
from supabase import create_client, Client

load_dotenv()

app = FastAPI(title="FaucetDrop Analytics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================== RESPONSE MODELS ======================

class FaucetMetaResponse(BaseModel):
    faucet_address: str
    chain_id: int
    network_name: str
    factory_address: Optional[str]
    factory_type: Optional[str]
    faucet_name: Optional[str]
    token_symbol: Optional[str]
    is_ether: bool
    is_claim_active: bool
    owner_address: Optional[str]
    start_time: Optional[int]
    updated_at: Optional[str]
    slug: Optional[str] 

class FaucetDetailResponse(BaseModel):
    faucet_address: str
    chain_id: int
    network_name: str
    factory_address: Optional[str]
    factory_type: Optional[str]
    faucet_name: Optional[str]
    token_address: Optional[str]
    token_symbol: Optional[str]
    token_decimals: int
    is_ether: bool
    balance: str
    claim_amount: str
    start_time: Optional[int]
    end_time: Optional[int]
    is_claim_active: bool
    is_paused: bool
    owner_address: Optional[str]
    use_backend: bool
    slug: Optional[str]
    image_url: Optional[str]
    description: Optional[str]
    updated_at: Optional[str]


class NetworkFaucetsResponse(BaseModel):
    chain_id: int
    network_name: str
    total: int
    faucets: List[FaucetMetaResponse]


class DashboardResponse(BaseModel):
    total_claims: int
    total_unique_users: int
    total_faucets: int
    total_transactions: int
    claims_pie_data: List[Dict]
    faucet_rankings: List[Dict]
    users_chart: List[Dict]
    network_transactions: List[Dict]
    network_faucets: List[Dict]
    last_updated: str


# ====================== ABIS ======================

FACTORY_ABI = [
  {"inputs": [], "stateMutability": "nonpayable", "type": "constructor"},
  {"inputs": [{"internalType": "address", "name": "faucet", "type": "address"}], "name": "FaucetDeletedError", "type": "error"},
  {"inputs": [], "name": "FaucetNotRegistered", "type": "error"},
  {"inputs": [], "name": "InvalidFaucet", "type": "error"},
  {"inputs": [{"internalType": "address", "name": "owner", "type": "address"}], "name": "OwnableInvalidOwner", "type": "error"},
  {"inputs": [{"internalType": "address", "name": "account", "type": "address"}], "name": "OwnableUnauthorizedAccount", "type": "error"},
  {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "faucet", "type": "address"}, {"indexed": False, "internalType": "address", "name": "owner", "type": "address"}, {"indexed": False, "internalType": "string", "name": "name", "type": "string"}, {"indexed": False, "internalType": "address", "name": "token", "type": "address"}, {"indexed": False, "internalType": "address", "name": "backend", "type": "address"}], "name": "FaucetCreated", "type": "event"},
  {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "faucet", "type": "address"}, {"indexed": True, "internalType": "address", "name": "initiator", "type": "address"}], "name": "FaucetDeleted", "type": "event"},
  {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "previousOwner", "type": "address"}, {"indexed": True, "internalType": "address", "name": "newOwner", "type": "address"}], "name": "OwnershipTransferred", "type": "event"},
  {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "faucet", "type": "address"}, {"indexed": False, "internalType": "string", "name": "transactionType", "type": "string"}, {"indexed": False, "internalType": "address", "name": "initiator", "type": "address"}, {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"}, {"indexed": False, "internalType": "bool", "name": "isEther", "type": "bool"}, {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}], "name": "TransactionRecorded", "type": "event"},
  {"inputs": [{"internalType": "string", "name": "_name", "type": "string"}, {"internalType": "address", "name": "_token", "type": "address"}, {"internalType": "address", "name": "_backend", "type": "address"}, {"internalType": "bool", "name": "_useBackend", "type": "bool"}], "name": "createFaucet", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "nonpayable", "type": "function"},
  {"inputs": [{"internalType": "address", "name": "_faucetAddress", "type": "address"}], "name": "deleteFaucet", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
  {"inputs": [], "name": "getAllFaucets", "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}], "stateMutability": "view", "type": "function"},
  {"inputs": [], "name": "getAllTransactions", "outputs": [{"components": [{"internalType": "address", "name": "faucetAddress", "type": "address"}, {"internalType": "string", "name": "transactionType", "type": "string"}, {"internalType": "address", "name": "initiator", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}, {"internalType": "bool", "name": "isEther", "type": "bool"}, {"internalType": "uint256", "name": "timestamp", "type": "uint256"}], "internalType": "struct TransactionLibrary.Transaction[]", "name": "", "type": "tuple[]"}], "stateMutability": "view", "type": "function"},
  {"inputs": [], "name": "getTotalFaucets", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
  {"inputs": [], "name": "getTotalTransactions", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
  {"inputs": [{"internalType": "address", "name": "user", "type": "address"}], "name": "getUserFaucets", "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}], "stateMutability": "view", "type": "function"},
  {"inputs": [], "name": "owner", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
  {"inputs": [{"internalType": "address", "name": "_faucetAddress", "type": "address"}, {"internalType": "string", "name": "_transactionType", "type": "string"}, {"internalType": "address", "name": "_initiator", "type": "address"}, {"internalType": "uint256", "name": "_amount", "type": "uint256"}, {"internalType": "bool", "name": "_isEther", "type": "bool"}], "name": "recordTransaction", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
  {"inputs": [], "name": "renounceOwnership", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
  {"inputs": [{"internalType": "address", "name": "_faucetAddress", "type": "address"}], "name": "resetAllClaims", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
  {"inputs": [{"internalType": "address", "name": "newOwner", "type": "address"}], "name": "transferOwnership", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
]

QUEST_FACTORY_ABI_MINIMAL = [
    {"inputs": [], "name": "getAllQuests", "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "getAllTransactions", "outputs": [{"components": [{"internalType": "address", "name": "faucetAddress", "type": "address"}, {"internalType": "string", "name": "transactionType", "type": "string"}, {"internalType": "address", "name": "initiator", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}, {"internalType": "bool", "name": "isEther", "type": "bool"}, {"internalType": "uint256", "name": "timestamp", "type": "uint256"}], "internalType": "struct TransactionLibrary.Transaction[]", "name": "", "type": "tuple[]"}], "stateMutability": "view", "type": "function"},
]

ERC20_ABI = [
    {"inputs": [{"internalType": "string", "name": "name_", "type": "string"}, {"internalType": "string", "name": "symbol_", "type": "string"}], "stateMutability": "nonpayable", "type": "constructor"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "owner", "type": "address"}, {"indexed": True, "internalType": "address", "name": "spender", "type": "address"}, {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"}], "name": "Approval", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "from", "type": "address"}, {"indexed": True, "internalType": "address", "name": "to", "type": "address"}, {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"}], "name": "Transfer", "type": "event"},
    {"inputs": [{"internalType": "address", "name": "owner", "type": "address"}, {"internalType": "address", "name": "spender", "type": "address"}], "name": "allowance", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "spender", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "decimals", "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "name", "outputs": [{"internalType": "string", "name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "symbol", "outputs": [{"internalType": "string", "name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "totalSupply", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "to", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "transfer", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "from", "type": "address"}, {"internalType": "address", "name": "to", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "transferFrom", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
]

FAUCET_ABI = [
    {"inputs": [{"internalType": "string", "name": "_name", "type": "string"}, {"internalType": "address", "name": "_token", "type": "address"}, {"internalType": "address", "name": "_backend", "type": "address"}, {"internalType": "bool", "name": "_useBackend", "type": "bool"}, {"internalType": "address", "name": "_owner", "type": "address"}, {"internalType": "address", "name": "_factory", "type": "address"}], "stateMutability": "nonpayable", "type": "constructor"},
    {"inputs": [], "name": "AlreadyClaimed", "type": "error"},
    {"inputs": [], "name": "ClaimAmountNotSet", "type": "error"},
    {"inputs": [], "name": "ClaimPeriodEnded", "type": "error"},
    {"inputs": [], "name": "ClaimPeriodNotStarted", "type": "error"},
    {"inputs": [], "name": "ContractPaused", "type": "error"},
    {"inputs": [{"internalType": "address", "name": "faucet", "type": "address"}], "name": "FaucetDeletedError", "type": "error"},
    {"inputs": [], "name": "InsufficientBalance", "type": "error"},
    {"inputs": [], "name": "InvalidAddress", "type": "error"},
    {"inputs": [], "name": "NotWhitelisted", "type": "error"},
    {"inputs": [], "name": "TransferFailed", "type": "error"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "user", "type": "address"}, {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"}, {"indexed": False, "internalType": "bool", "name": "isEther", "type": "bool"}], "name": "Claimed", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "funder", "type": "address"}, {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"}, {"indexed": False, "internalType": "uint256", "name": "backendFee", "type": "uint256"}, {"indexed": False, "internalType": "bool", "name": "isEther", "type": "bool"}], "name": "Funded", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "previousOwner", "type": "address"}, {"indexed": True, "internalType": "address", "name": "newOwner", "type": "address"}], "name": "OwnershipTransferred", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "owner", "type": "address"}, {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"}, {"indexed": False, "internalType": "bool", "name": "isEther", "type": "bool"}], "name": "Withdrawn", "type": "event"},
    {"inputs": [], "name": "BACKEND", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "BACKEND_FEE_PERCENT", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "_admin", "type": "address"}], "name": "addAdmin", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address[]", "name": "users", "type": "address[]"}], "name": "claim", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "claimAmount", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address[]", "name": "users", "type": "address[]"}], "name": "claimWhenActive", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "deleteFaucet", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "deleted", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "endTime", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "factory", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "_tokenAmount", "type": "uint256"}], "name": "fund", "outputs": [], "stateMutability": "payable", "type": "function"},
    {"inputs": [], "name": "getAllClaims", "outputs": [{"components": [{"internalType": "address", "name": "recipient", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}, {"internalType": "uint256", "name": "timestamp", "type": "uint256"}], "internalType": "struct FaucetDrops.ClaimDetail[]", "name": "", "type": "tuple[]"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "user", "type": "address"}], "name": "getClaimStatus", "outputs": [{"internalType": "bool", "name": "claimed", "type": "bool"}, {"internalType": "bool", "name": "whitelisted", "type": "bool"}, {"internalType": "bool", "name": "canClaim", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "user", "type": "address"}], "name": "getDetailedClaimStatus", "outputs": [{"internalType": "bool", "name": "claimed", "type": "bool"}, {"internalType": "bool", "name": "whitelisted", "type": "bool"}, {"internalType": "bool", "name": "canClaim", "type": "bool"}, {"internalType": "uint256", "name": "claimAmountForUser", "type": "uint256"}, {"internalType": "bool", "name": "hasCustom", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "getFaucetBalance", "outputs": [{"internalType": "uint256", "name": "balance", "type": "uint256"}, {"internalType": "bool", "name": "isEther", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "getUseBackend", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "", "type": "address"}], "name": "hasClaimed", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "isClaimActive", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "name", "outputs": [{"internalType": "string", "name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "owner", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "paused", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "_admin", "type": "address"}], "name": "removeAdmin", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "renounceOwnership", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "resetAllClaimed", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address[]", "name": "users", "type": "address[]"}], "name": "resetClaimedBatch", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "user", "type": "address"}], "name": "resetClaimedSingle", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "_claimAmount", "type": "uint256"}, {"internalType": "uint256", "name": "_startTime", "type": "uint256"}, {"internalType": "uint256", "name": "_endTime", "type": "uint256"}], "name": "setClaimParameters", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "user", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "setCustomClaimAmount", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address[]", "name": "users", "type": "address[]"}, {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}], "name": "setCustomClaimAmountsBatch", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "bool", "name": "_paused", "type": "bool"}], "name": "setPaused", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "user", "type": "address"}, {"internalType": "bool", "name": "status", "type": "bool"}], "name": "setWhitelist", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address[]", "name": "users", "type": "address[]"}, {"internalType": "bool", "name": "status", "type": "bool"}], "name": "setWhitelistBatch", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "startTime", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "token", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "newOwner", "type": "address"}], "name": "transferOwnership", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "string", "name": "_newName", "type": "string"}], "name": "updateName", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "useBackend", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "user", "type": "address"}], "name": "userHasCustomAmount", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "withdraw", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"stateMutability": "payable", "type": "receive"},
]

CHECKIN_ABI = [
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "user", "type": "address"}, {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}, {"indexed": False, "internalType": "uint256", "name": "balance", "type": "uint256"}], "name": "CheckIn", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "user", "type": "address"}, {"indexed": False, "internalType": "uint256", "name": "participantCount", "type": "uint256"}], "name": "NewParticipant", "type": "event"},
    {"inputs": [], "name": "droplist", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "getAllParticipants", "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "user", "type": "address"}], "name": "getBalance", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "getTotalTransactions", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "getUniqueParticipantCount", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "user", "type": "address"}], "name": "hasAddressParticipated", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
]


# ====================== CHAIN CONFIGS ======================

NETWORK_COLORS: Dict[str, str] = {
    "Celo":      "#35D07F",
    "Lisk":      "#0D4477",
    "Arbitrum":  "#28A0F0",
    "Base":      "#0052FF",
    "BNB":       "#F3BA2F",
    "Avalanche": "#E84142",
}

CHAIN_CONFIGS: Dict[int, Dict] = {
    42220: {
        "name": "Celo",
        "rpcUrls": ["https://forno.celo.org", "https://celo-mainnet.g.alchemy.com/v2/sXHCrL5-xwYkPtkRC_WTEZHvIkOVTbw-", "https://celo-mainnet.infura.io/v3/e9fa8c3350054dafa40019a5b604679f"],
        "factoryAddresses": ["0x17cFed7fEce35a9A71D60Fbb5CA52237103A21FB", "0xB8De8f37B263324C44FD4874a7FB7A0C59D8C58E", "0xc26c4Ea50fd3b63B6564A5963fdE4a3A474d4024", "0x9D6f441b31FBa22700bb3217229eb89b13FB49de", "0xE3Ac30fa32E727386a147Fe08b4899Da4115202f", "0xF8707b53a2bEc818E96471DDdb34a09F28E0dE6D", "0x8D1306b3970278b3AB64D1CE75377BDdf00f61da", "0x8cA5975Ded3B2f93E188c05dD6eb16d89b14aeA5", "0xc9c89f695C7fa9D9AbA3B297C9b0d86C5A74f534"],
        "nativeCurrency": {"symbol": "CELO", "decimals": 18},
        "blockExplorer": "https://celoscan.io/",
    },
    1135: {
        "name": "Lisk",
        "rpcUrls": ["https://rpc.api.lisk.com", "https://lisk.drpc.org", "https://1rpc.io/lisk"],
        "factoryAddresses": ["0x96E9911df17e94F7048cCbF7eccc8D9b5eDeCb5C", "0x4F5Cf906b9b2Bf4245dba9F7d2d7F086a2a441C2", "0x21E855A5f0E6cF8d0CfE8780eb18e818950dafb7", "0xd6Cb67dF496fF739c4eBA2448C1B0B44F4Cf0a7C", "0x0837EACf85472891F350cba74937cB02D90E60A4"],
        "nativeCurrency": {"symbol": "ETH", "decimals": 18},
        "blockExplorer": "https://blockscout.lisk.com/",
    },
    42161: {
        "name": "Arbitrum",
        "rpcUrls": ["https://arb1.arbitrum.io/rpc", "https://arb-mainnet.g.alchemy.com/v2/sXHCrL5-xwYkPtkRC_WTEZHvIkOVTbw-", "https://arbitrum.infura.io/v3/e9fa8c3350054dafa40019a5b604679f"],
        "factoryAddresses": ["0x0a5C19B5c0f4B9260f0F8966d26bC05AAea2009C", "0x42355492298A89eb1EF7FB2fFE4555D979f1Eee9", "0x9D6f441b31FBa22700bb3217229eb89b13FB49de"],
        "nativeCurrency": {"symbol": "ETH", "decimals": 18},
        "blockExplorer": "https://arbiscan.io/",
    },
    8453: {
        "name": "Base",
        "rpcUrls": ["https://base.publicnode.com", "https://mainnet.base.org", "https://base-mainnet.g.alchemy.com/v2/sXHCrL5-xwYkPtkRC_WTEZHvIkOVTbw-"],
        "factoryAddresses": ["0x945431302922b69D500671201CEE62900624C6d5", "0xda191fb5Ca50fC95226f7FC91C792927FC968CA9", "0x587b840140321DD8002111282748acAdaa8fA206"],
        "nativeCurrency": {"symbol": "ETH", "decimals": 18},
        "blockExplorer": "https://basescan.org/",
    },
    56: {
        "name": "BNB",
        "rpcUrls": ["https://bnb-mainnet.g.alchemy.com/v2/sXHCrL5-xwYkPtkRC_WTEZHvIkOVTbw-", "https://bsc-dataseed.binance.org/", "https://rpc.ankr.com/bsc"],
        "factoryAddresses": ["0xFE7DB2549d0c03A4E3557e77c8d798585dD80Cc1", "0x0F779235237Fc136c6EE9dD9bC2545404CDeAB36", "0x4B8c7A12660C4847c65662a953F517198fBFc0ED"],
        "nativeCurrency": {"symbol": "BNB", "decimals": 18},
        "blockExplorer": "https://bscscan.com/",
    },
    43114: {
        "name": "Avalanche",
        "rpcUrls": ["https://api.avax.network/ext/bc/C/rpc", "https://avax-mainnet.g.alchemy.com/v2/sXHCrL5-xwYkPtkRC_WTEZHvIkOVTbw-"],
        "factoryAddresses": [],
        "nativeCurrency": {"symbol": "AVAX", "decimals": 18},
        "blockExplorer": "https://snowtrace.io/",
    },
}

CHAIN_CONFIGS_V2: Dict[int, Dict] = {
    42220: {
        "name": "Celo",
        "rpcUrls": CHAIN_CONFIGS[42220]["rpcUrls"],
        "factories": {
            "0x17cFed7fEce35a9A71D60Fbb5CA52237103A21FB": "dropcode",
            "0x9D6f441b31FBa22700bb3217229eb89b13FB49de": "dropcode",
            "0xE3Ac30fa32E727386a147Fe08b4899Da4115202f": "dropcode",
            "0xF8707b53a2bEc818E96471DDdb34a09F28E0dE6D": "droplist",
            "0x8D1306b3970278b3AB64D1CE75377BDdf00f61da": "dropcode",
            "0x8cA5975Ded3B2f93E188c05dD6eb16d89b14aeA5": "custom",
            "0xc9c89f695C7fa9D9AbA3B297C9b0d86C5A74f534": "droplist",
        },
    },
    1135: {
        "name": "Lisk",
        "rpcUrls": CHAIN_CONFIGS[1135]["rpcUrls"],
        "factories": {
            "0x21E855A5f0E6cF8d0CfE8780eb18e818950dafb7": "custom",
            "0xd6Cb67dF496fF739c4eBA2448C1B0B44F4Cf0a7C": "dropcode",
            "0x0837EACf85472891F350cba74937cB02D90E60A4": "droplist",
        },
    },
    42161: {
        "name": "Arbitrum",
        "rpcUrls": CHAIN_CONFIGS[42161]["rpcUrls"],
        "factories": {
            "0x0a5C19B5c0f4B9260f0F8966d26bC05AAea2009C": "dropcode",
            "0x42355492298A89eb1EF7FB2fFE4555D979f1Eee9": "droplist",
            "0x9D6f441b31FBa22700bb3217229eb89b13FB49de": "custom",
        },
    },
    8453: {
        "name": "Base",
        "rpcUrls": CHAIN_CONFIGS[8453]["rpcUrls"],
        "factories": {
            "0x945431302922b69D500671201CEE62900624C6d5": "dropcode",
            "0xda191fb5Ca50fC95226f7FC91C792927FC968CA9": "droplist",
            "0x587b840140321DD8002111282748acAdaa8fA206": "custom",
        },
    },
    56: {
        "name": "BNB",
        "rpcUrls": CHAIN_CONFIGS[56]["rpcUrls"],
        "factories": {
            "0xFE7DB2549d0c03A4E3557e77c8d798585dD80Cc1": "dropcode",
            "0x0F779235237Fc136c6EE9dD9bC2545404CDeAB36": "droplist",
            "0x4B8c7A12660C4847c65662a953F517198fBFc0ED": "custom",
        },
    },
    43114: {
        "name": "Avalanche",
        "rpcUrls": CHAIN_CONFIGS[43114]["rpcUrls"],
        "factories": {},
    },
}

NATIVE_SYMBOLS: Dict[int, str] = {
    42220: "CELO",
    1135:  "ETH",
    42161: "ETH",
    8453:  "ETH",
    56:    "BNB",
    43114: "AVAX",
}


# ====================== SUPABASE ======================

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

supabase: Client = None
if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)
    print("✅ Supabase connected successfully")
else:
    print("⚠️  WARNING: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not found in .env")


# ====================== GLOBAL DASHBOARD CACHE ======================

dashboard_data: Dict[str, Any] = {
    "total_claims": 0,
    "total_unique_users": 0,
    "total_faucets": 0,
    "total_transactions": 0,
    "claims_pie_data": [],
    "faucet_rankings": [],
    "users_chart": [],
    "network_transactions": [],
    "network_faucets": [],
    "last_updated": None,
}


# ====================== SHARED HELPERS ======================

def get_web3(rpc_urls: list) -> Web3:
    for url in rpc_urls:
        try:
            w3 = Web3(Web3.HTTPProvider(url))
            if w3.is_connected():
                return w3
        except Exception:
            continue
    raise Exception("All RPCs failed")


def is_placeholder_address(addr: str) -> bool:
    stripped = addr.replace("0x", "").replace(".", "")
    return len(stripped) == 0 or set(stripped) == {"0"}


def safe_checksum(w3: Web3, addr: str) -> Optional[str]:
    try:
        return w3.to_checksum_address(addr)
    except Exception:
        return None


def _safe_call(contract, fn_name: str):
    try:
        return contract.functions[fn_name]().call()
    except Exception:
        return None


def _chunks(lst: List, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def fetch_deleted_faucets() -> set:
    try:
        r = requests.get("https://faucetdrop-backend.onrender.com/deleted-faucets", timeout=5)
        if r.ok:
            return {a.lower() for a in r.json().get("deletedAddresses", [])}
    except Exception:
        pass
    return set()


def get_faucet_name_sync(w3: Web3, addr_checksum: str) -> str:
    short = f"Faucet {addr_checksum[:6]}...{addr_checksum[-4:]}"
    try:
        contract = w3.eth.contract(address=addr_checksum, abi=FAUCET_ABI)
        name = contract.functions.name().call()
        return name if name and name.strip() else short
    except Exception:
        return short


def _try_checkin(w3: Web3, addr_checksum: str):
    try:
        contract = w3.eth.contract(address=addr_checksum, abi=CHECKIN_ABI)
        tx_count = contract.functions.getTotalTransactions().call()
        participants = [p.lower() for p in contract.functions.getAllParticipants().call() if p]
        return tx_count, participants
    except Exception:
        return 0, []


def detect_and_call(w3: Web3, address_checksum: str):
    try:
        contract = w3.eth.contract(address=address_checksum, abi=FACTORY_ABI)
        factory_txs = contract.functions.getAllTransactions().call()
        faucets = contract.functions.getAllFaucets().call()
        return ("factory", factory_txs, faucets)
    except Exception:
        pass
    try:
        contract = w3.eth.contract(address=address_checksum, abi=QUEST_FACTORY_ABI_MINIMAL)
        factory_txs = contract.functions.getAllTransactions().call()
        faucets = contract.functions.getAllQuests().call()
        return ("quest", factory_txs, faucets)
    except Exception:
        pass
    try:
        contract = w3.eth.contract(address=address_checksum, abi=CHECKIN_ABI)
        tx_count = contract.functions.getTotalTransactions().call()
        participants = contract.functions.getAllParticipants().call()
        return ("checkin", tx_count, [p.lower() for p in participants if p])
    except Exception:
        pass
    return ("unknown", None, None)


def _get_all_faucets_from_factory(w3: Web3, factory_cs: str) -> List[str]:
    for fn_name in ("getAllFaucets", "getAllQuests"):
        try:
            abi_stub = [{"inputs": [], "name": fn_name, "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}], "stateMutability": "view", "type": "function"}]
            c = w3.eth.contract(address=factory_cs, abi=abi_stub)
            return c.functions[fn_name]().call()
        except Exception:
            continue
    return []

def _make_slug(name: str, address: str) -> str:
    import re
    name_part = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    addr_suffix = address.lower()[-4:]   # always appended for uniqueness
    return f"{name_part}-{addr_suffix}" if name_part else addr_suffix
# ====================== FAUCET DETAIL FETCHER ======================

def fetch_faucet_details_sync(
    w3: Web3,
    faucet_address: str,
    factory_address: str,
    factory_type: str,
    chain_id: int,
) -> Optional[Dict]:
    try:
        checksum = w3.to_checksum_address(faucet_address)
        contract = w3.eth.contract(address=checksum, abi=FAUCET_ABI)

        deleted_flag = _safe_call(contract, "deleted") or False
        if deleted_flag:
            return None

        name            = _safe_call(contract, "name")          or f"Faucet {faucet_address[:6]}...{faucet_address[-4:]}"
        owner           = _safe_call(contract, "owner")         or ""
        token_addr      = _safe_call(contract, "token")         or "0x0000000000000000000000000000000000000000"
        claim_amount    = _safe_call(contract, "claimAmount")   or 0
        start_time      = _safe_call(contract, "startTime")     or 0
        end_time        = _safe_call(contract, "endTime")       or 0
        is_claim_active = _safe_call(contract, "isClaimActive") or False
        is_paused       = _safe_call(contract, "paused")        or False
        use_backend     = _safe_call(contract, "useBackend")    or False
        
        balance_tuple = _safe_call(contract, "getFaucetBalance")
        balance   = str(balance_tuple[0]) if balance_tuple else "0"
        is_ether  = bool(balance_tuple[1]) if balance_tuple else False

        token_symbol   = NATIVE_SYMBOLS.get(chain_id, "ETH") if is_ether else "TOKEN"
        token_decimals = 18
        zero_addr      = "0x0000000000000000000000000000000000000000"

        if not is_ether and token_addr.lower() != zero_addr:
            try:
                tok = w3.eth.contract(address=w3.to_checksum_address(token_addr), abi=ERC20_ABI)
                token_symbol   = _safe_call(tok, "symbol")   or token_symbol
                token_decimals = _safe_call(tok, "decimals") or 18
            except Exception:
                pass

        return {
            "faucet_address":  faucet_address.lower(),
            "chain_id":        chain_id,
            "network_name":    CHAIN_CONFIGS_V2.get(chain_id, {}).get("name", str(chain_id)),
            "factory_address": factory_address.lower(),
            "factory_type":    factory_type,
            "faucet_name":     name,
            "token_address":   token_addr.lower(),
            "token_symbol":    token_symbol,
            "token_decimals":  int(token_decimals),
            "is_ether":        is_ether,
            "balance":         balance,
            "claim_amount":    str(claim_amount),
            "start_time":      int(start_time),
            "end_time":        int(end_time),
            "is_claim_active": is_claim_active,
            "is_paused":       is_paused,
            "owner_address":   owner.lower() if owner else "",
            "use_backend":     use_backend,
            "slug":            _make_slug(name, faucet_address),
            "image_url":       "",
            "description":     "",
        }
    except Exception as e:
        print(f"   ⚠️  fetch_faucet_details_sync({faucet_address}): {e}")
        return None


async def _enrich_with_metadata(rows: List[Dict]) -> List[Dict]:
    async def _fetch_one(row: Dict) -> Dict:
        addr = row["faucet_address"]
        try:
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    f"https://faucetdrop-backend.onrender.com/faucet-metadata/{addr}",
                    timeout=4,
                ),
            )
            if resp.ok:
                meta = resp.json()
                row["image_url"]   = meta.get("imageUrl", "")
                row["description"] = meta.get("description", "")
        except Exception:
            pass
        return row

    return await asyncio.gather(*[_fetch_one(r) for r in rows])


# ====================== SUPABASE SAVE HELPER ======================

def save_dashboard_to_supabase(data: Dict[str, Any]) -> None:
    """
    Persists ALL dashboard fields to Supabase so the frontend can
    read them directly without going through the backend at all.

    Tables written:
      faucet_data      — network → faucet count + chain_id + color
      user_data        — date → new_users + cumulative_users
      claim_data       — per-faucet claims + total_transactions + rank
      network_tx_data  — network → total_transactions + chain_id + color
      dashboard_meta   — single-row snapshot of scalar totals + last_updated
    """
    if not supabase:
        return

    now_iso = data.get("last_updated") or datetime.utcnow().isoformat()

    try:
        # ── 1. faucet_data (network counts) ──────────────────────────────────
        faucet_rows = [
            {
                "network":  item["network"],
                "faucets":  item["faucets"],
                "chain_id": next(
                    (cid for cid, cfg in CHAIN_CONFIGS.items() if cfg["name"] == item["network"]),
                    0,
                ),
                "color":    NETWORK_COLORS.get(item["network"], "#888888"),
            }
            for item in data["network_faucets"]
        ]
        for chunk in _chunks(faucet_rows, 100):
            supabase.table("faucet_data").upsert(chunk, on_conflict="network").execute()

        # ── 2. user_data (per-date new + cumulative users) ───────────────────
        user_rows = [
            {
                "date":             item["date"],
                "new_users":        item["newUsers"],
                "cumulative_users": item["cumulativeUsers"],
            }
            for item in data["users_chart"]
        ]
        for chunk in _chunks(user_rows, 100):
            supabase.table("user_data").upsert(chunk, on_conflict="date").execute()

        # ── 3. claim_data (per-faucet stats — NOW includes total_transactions) 
        claim_rows = [
            {
                "faucet_address":    item["faucetAddress"],
                "faucet_name":       item["faucetName"],
                "network":           item["network"],
                "chain_id":          item["chainId"],
                "rank":              item["rank"],
                "claims":            item["totalClaims"],
                "total_transactions": item["totalClaims"],   # same as claims for now; extend later
                "total_amount":      "0",
                "latest_claim_time": item["latestClaimTime"],
                "updated_at":        now_iso,
            }
            for item in data["faucet_rankings"]
        ]
        for chunk in _chunks(claim_rows, 100):
            supabase.table("claim_data").upsert(chunk, on_conflict="faucet_address").execute()

        # ── 4. network_tx_data (per-network transaction totals) ──────────────
        #    This is a NEW table — create it in Supabase if it doesn't exist:
        #    CREATE TABLE network_tx_data (
        #      network TEXT PRIMARY KEY, total_transactions INT,
        #      chain_id INT, color TEXT, updated_at TIMESTAMPTZ
        #    );
        net_tx_rows = [
            {
                "network":            item["name"],
                "total_transactions": item["totalTransactions"],
                "chain_id":           item["chainId"],
                "color":              item["color"],
                "updated_at":         now_iso,
            }
            for item in data["network_transactions"]
        ]
        for chunk in _chunks(net_tx_rows, 100):
            supabase.table("network_tx_data").upsert(chunk, on_conflict="network").execute()

        # ── 5. dashboard_meta (scalar totals snapshot) ───────────────────────
        #    CREATE TABLE dashboard_meta (
        #      id INT PRIMARY KEY DEFAULT 1,
        #      total_claims INT, total_unique_users INT,
        #      total_faucets INT, total_transactions INT,
        #      last_updated TIMESTAMPTZ
        #    );
        supabase.table("dashboard_meta").upsert(
            {
                "id":                 1,
                "total_claims":       data["total_claims"],
                "total_unique_users": data["total_unique_users"],
                "total_faucets":      data["total_faucets"],
                "total_transactions": data["total_transactions"],
                "last_updated":       now_iso,
            },
            on_conflict="id",
        ).execute()

        print(f"✅ [save_dashboard_to_supabase] all tables updated at {now_iso}")

        # ── 6. Evict deleted faucets from dashboard tables ───────────────────
        # Fetch the current deleted list and remove any stale rows so deleted
        # faucets don't linger in claim_data / faucet stats.
        try:
            r = requests.get("https://faucetdrop-backend.onrender.com/deleted-faucets", timeout=5)
            if r.ok:
                deleted_addrs = {a.lower() for a in r.json().get("deletedAddresses", [])}
                for addr in deleted_addrs:
                    supabase.table("claim_data").delete().eq("faucet_address", addr).execute()
                if deleted_addrs:
                    print(f"   🗑️  Evicted {len(deleted_addrs)} deleted faucets from claim_data")
        except Exception as evict_err:
            print(f"   ⚠️  Eviction step failed: {evict_err}")

    except Exception as e:
        print(f"⚠️  [save_dashboard_to_supabase] failed: {e}")


# ====================== BACKGROUND JOB: network_faucets + faucet_details ======================

async def refresh_network_faucets():
    """
    Crawls every chain → every typed factory → every faucet.
    Writes slug to both `network_faucets` and `faucet_details` in Supabase.
    """
    print(f"🔄 [refresh_network_faucets] started at {datetime.utcnow()}")

    deleted_set: set = set()
    try:
        r = requests.get("https://faucetdrop-backend.onrender.com/deleted-faucets", timeout=5)
        if r.ok:
            deleted_set = {a.lower() for a in r.json().get("deletedAddresses", [])}
    except Exception:
        pass

    for chain_id, cfg in CHAIN_CONFIGS_V2.items():
        factories_map: Dict[str, str] = cfg.get("factories", {})
        if not factories_map:
            continue

        try:
            w3 = get_web3(cfg["rpcUrls"])
        except Exception as e:
            print(f"   ⚠️  {cfg['name']}: all RPCs failed — {e}")
            continue

        meta_rows:   List[Dict] = []
        detail_rows: List[Dict] = []

        for factory_addr, factory_type in factories_map.items():
            if is_placeholder_address(factory_addr):
                continue
            factory_cs = safe_checksum(w3, factory_addr)
            if not factory_cs:
                continue

            faucet_list = _get_all_faucets_from_factory(w3, factory_cs)
            print(f"   📋 {cfg['name']}/{factory_cs[:10]}... ({factory_type}): {len(faucet_list)} faucets")

            for faucet_raw in faucet_list:
                faucet_cs = safe_checksum(w3, faucet_raw)
                if not faucet_cs or faucet_cs.lower() in deleted_set:
                    continue

                detail = fetch_faucet_details_sync(w3, faucet_cs, factory_addr, factory_type, chain_id)
                if detail is None:
                    continue

                detail_rows.append(detail)
                meta_rows.append({
                    "faucet_address":  detail["faucet_address"],
                    "chain_id":        chain_id,
                    "network_name":    cfg["name"],
                    "factory_address": factory_addr.lower(),
                    "factory_type":    factory_type,
                    "faucet_name":     detail["faucet_name"],
                    "slug":            detail["slug"],     # ← NEW
                    "token_symbol":    detail["token_symbol"],
                    "is_ether":        detail["is_ether"],
                    "is_claim_active": detail["is_claim_active"],
                    "owner_address":   detail["owner_address"],
                    "start_time":      detail["start_time"],
                })

        detail_rows = await _enrich_with_metadata(detail_rows)

        if supabase and meta_rows:
            try:
                for chunk in _chunks(meta_rows, 100):
                    supabase.table("network_faucets").upsert(chunk, on_conflict="faucet_address").execute()
                for chunk in _chunks(detail_rows, 100):
                    supabase.table("faucet_details").upsert(chunk, on_conflict="faucet_address").execute()
                print(f"   ✅ {cfg['name']}: saved {len(meta_rows)} faucets with slugs")
            except Exception as e:
                print(f"   ⚠️  {cfg['name']}: Supabase upsert failed — {e}")

    # Evict deleted faucets
    if supabase and deleted_set:
        for addr in deleted_set:
            try:
                supabase.table("network_faucets").delete().eq("faucet_address", addr).execute()
                supabase.table("faucet_details").delete().eq("faucet_address", addr).execute()
            except Exception:
                pass

    print(f"✅ [refresh_network_faucets] done")


# ====================== BACKGROUND JOB: dashboard ======================

async def refresh_all_data():
    global dashboard_data
    print(f"🔄 [refresh_all_data] started at {datetime.utcnow()}")

    all_claims           = []
    all_txs_count        = 0
    network_stats        = []
    network_faucets_list = []
    unique_users: set    = set()
    faucet_stats         = {}   # only NON-deleted faucets tracked here (for claims/count)

    # ── Fetch deleted set ONCE up front ─────────────────────────────────────
    # Rule: deleted faucets are excluded from faucet counts and claim stats,
    #       but their historical transactions are still counted in tx totals.
    deleted = await fetch_deleted_faucets()
    print(f"   🗑️  Deleted faucets to exclude from counts/claims: {len(deleted)}")

    for chain_id, cfg in CHAIN_CONFIGS.items():
        chain_name  = cfg["name"]
        chain_color = NETWORK_COLORS.get(chain_name, "#888888")

        try:
            w3 = get_web3(cfg["rpcUrls"])
        except Exception as e:
            print(f"⚠️  {chain_name}: All RPCs failed — {e}")
            network_stats.append({"name": chain_name, "chainId": chain_id, "totalTransactions": 0, "color": chain_color})
            network_faucets_list.append({"network": chain_name, "faucets": 0})
            continue

        chain_tx_count     = 0   # ALL txs including from deleted faucets
        chain_faucet_count = 0   # only NON-deleted faucets
        chain_claim_txs    = []

        for factory_addr in cfg["factoryAddresses"]:
            if is_placeholder_address(factory_addr):
                continue
            addr_checksum = safe_checksum(w3, factory_addr)
            if not addr_checksum:
                continue

            contract_type, data_a, data_b = detect_and_call(w3, addr_checksum)

            if contract_type in ("factory", "quest"):
                factory_txs      = data_a
                faucet_addresses = data_b

                # ✅ Count ALL transactions (including from deleted faucets)
                chain_tx_count += len(factory_txs)

                # Collect claim txs — will filter deleted faucets below
                claims = [tx for tx in factory_txs if "claim" in str(tx[1]).lower()]
                chain_claim_txs.extend(claims)
                label = "QUEST" if contract_type == "quest" else "FACTORY"
                print(f"   📋 {chain_name}/{addr_checksum[:10]}... {label}: {len(factory_txs)} txs, {len(claims)} claims")

                # ✅ Count only NON-deleted faucets
                for faucet_raw in faucet_addresses:
                    faucet_cs = safe_checksum(w3, faucet_raw)
                    if not faucet_cs:
                        continue
                    addr_lower = faucet_cs.lower()

                    if addr_lower in deleted:
                        print(f"      🗑️  Skipping deleted faucet {addr_lower[:10]}... from count")
                        continue

                    chain_faucet_count += 1
                    if addr_lower not in faucet_stats:
                        faucet_stats[addr_lower] = {
                            "claims": 0, "latest": 0, "name": "",
                            "network": chain_name, "chainId": chain_id,
                            "w3": w3, "addr_checksum": faucet_cs, "checkin_txs": 0,
                        }

            elif contract_type == "checkin":
                tx_count     = data_a
                participants = data_b
                addr_lower   = addr_checksum.lower()

                # ✅ Always count checkin txs regardless of deleted status
                chain_tx_count += tx_count

                if addr_lower not in deleted:
                    # Only count as a faucet + track participants if NOT deleted
                    chain_faucet_count += 1
                    before = len(unique_users)
                    unique_users.update(participants)
                    print(f"   🔄 {chain_name}/{addr_checksum[:10]}... CHECKIN: {tx_count} txs, {len(participants)} participants (+{len(unique_users)-before} new unique)")
                    if addr_lower not in faucet_stats:
                        faucet_stats[addr_lower] = {
                            "claims": 0, "latest": 0, "name": "",
                            "network": chain_name, "chainId": chain_id,
                            "w3": w3, "addr_checksum": addr_checksum, "checkin_txs": tx_count,
                        }
                    else:
                        faucet_stats[addr_lower]["checkin_txs"] = tx_count
                        unique_users.update(participants)
                else:
                    print(f"   🗑️  {chain_name}/{addr_checksum[:10]}... CHECKIN deleted — txs counted, faucet excluded")
            else:
                print(f"   ❓ {chain_name}/{addr_checksum[:10]}... unknown, skipping")

        # ── Process claim txs — filter deleted faucets for CLAIMS only ──────
        for tx in chain_claim_txs:
            faucet_cs = safe_checksum(w3, str(tx[0]))
            if not faucet_cs:
                continue
            addr_lower = faucet_cs.lower()

            if addr_lower in deleted:
                # ✅ Deleted faucet: skip its claims but its txs were already counted above
                continue

            claimer_cs = safe_checksum(w3, str(tx[2]))
            if claimer_cs:
                unique_users.add(claimer_cs.lower())
            all_claims.append(tx)
            if addr_lower not in faucet_stats:
                faucet_stats[addr_lower] = {
                    "claims": 0, "latest": 0, "name": "",
                    "network": chain_name, "chainId": chain_id,
                    "w3": w3, "addr_checksum": faucet_cs, "checkin_txs": 0,
                }
            faucet_stats[addr_lower]["claims"] += 1
            faucet_stats[addr_lower]["latest"]  = max(faucet_stats[addr_lower]["latest"], int(tx[5]))

        # ── Checkin fallback for faucets with no claims yet ──────────────────
        for addr_lower, stats in faucet_stats.items():
            if stats["chainId"] != chain_id or stats["claims"] > 0 or stats["checkin_txs"] > 0:
                continue
            checkin_count, checkin_participants = _try_checkin(stats["w3"], stats["addr_checksum"])
            if checkin_count > 0:
                stats["checkin_txs"]  = checkin_count
                chain_tx_count       += checkin_count
                before = len(unique_users)
                unique_users.update(checkin_participants)
                print(f"      🔄 CHECKIN fallback {stats['addr_checksum'][:10]}...: {checkin_count} txs (+{len(unique_users)-before} new unique)")

        all_txs_count += chain_tx_count
        network_stats.append({"name": chain_name, "chainId": chain_id, "totalTransactions": chain_tx_count, "color": chain_color})
        network_faucets_list.append({"network": chain_name, "faucets": chain_faucet_count})
        print(f"   ✅ {chain_name}: {chain_tx_count} txs (all), {chain_faucet_count} active faucets")

    print(f"🔤 Fetching names for {len(faucet_stats)} faucets...")
    for addr_lower, stats in faucet_stats.items():
        stats["name"] = get_faucet_name_sync(stats["w3"], stats["addr_checksum"])

    # ── User chart ───────────────────────────────────────────────────────────
    first_claim_per_user = {}
    for tx in all_claims:
        claimer  = str(tx[2]).lower()
        date_str = datetime.fromtimestamp(int(tx[5])).strftime("%Y-%m-%d")
        if claimer not in first_claim_per_user or date_str < first_claim_per_user[claimer]:
            first_claim_per_user[claimer] = date_str

    new_users_by_date = defaultdict(int)
    for date_str in first_claim_per_user.values():
        new_users_by_date[date_str] += 1

    users_chart = []
    cumulative  = 0
    for date_str in sorted(new_users_by_date.keys()):
        new = new_users_by_date[date_str]
        cumulative += new
        users_chart.append({"date": date_str, "newUsers": new, "cumulativeUsers": cumulative})

    # ── Rankings + pie ───────────────────────────────────────────────────────
    total_claims   = len(all_claims)
    sorted_faucets = sorted(faucet_stats.items(), key=lambda x: x[1]["latest"], reverse=True)
    rankings = [
        {
            "rank":            i + 1,
            "faucetAddress":   addr,
            "faucetName":      stats["name"],
            "network":         stats["network"],
            "chainId":         stats["chainId"],
            "totalClaims":     stats["claims"],
            "latestClaimTime": stats["latest"],
        }
        for i, (addr, stats) in enumerate(sorted_faucets)
    ]

    sorted_by_claims = sorted(faucet_stats.items(), key=lambda x: x[1]["claims"], reverse=True)
    pie = [
        {
            "name":         stats["name"],
            "value":        stats["claims"],
            "faucetAddress": addr,
            "network":      stats["network"],
        }
        for addr, stats in sorted_by_claims[:10]
    ]
    others_count   = sum(s["claims"] for _, s in sorted_by_claims[10:])
    others_faucets = len(sorted_by_claims) - 10
    if others_count > 0:
        pie.append({"name": f"Others ({others_faucets})", "value": others_count, "faucetAddress": "others", "network": ""})

    # ── Assemble final dict ──────────────────────────────────────────────────
    dashboard_data = {
        "total_claims":         total_claims,
        "total_unique_users":   len(unique_users),
        "total_faucets":        sum(x["faucets"] for x in network_faucets_list),
        "total_transactions":   all_txs_count,
        "claims_pie_data":      pie,
        "faucet_rankings":      rankings,
        "users_chart":          users_chart,
        "network_transactions": network_stats,
        "network_faucets":      network_faucets_list,
        "last_updated":         datetime.utcnow().isoformat(),
    }

    print(f"✅ Done: {total_claims} claims | {len(unique_users)} unique users | {dashboard_data['total_faucets']} faucets | {all_txs_count} txs")

    # ── Persist everything to Supabase ───────────────────────────────────────
    save_dashboard_to_supabase(dashboard_data)


# ====================== SCHEDULER ======================
# Auto-refresh every 3 hours. Frontend manual refresh hits /api/refresh directly.

scheduler = AsyncIOScheduler()
scheduler.add_job(refresh_all_data,        "interval", hours=3)
scheduler.add_job(refresh_network_faucets, "interval", hours=3)
scheduler.start()


# ====================== SUPABASE DASHBOARD LOADER ======================

def load_from_supabase() -> Optional[dict]:
    """
    Reads ALL dashboard data from Supabase.
    Uses the new network_tx_data and dashboard_meta tables when available,
    falls back gracefully to computing from claim_data.
    """
    # ── Scalar totals from dashboard_meta ────────────────────────────────────
    meta_rows = supabase.table("dashboard_meta").select("*").eq("id", 1).execute().data
    meta = meta_rows[0] if meta_rows else {}

    # ── faucet_data ───────────────────────────────────────────────────────────
    faucet_rows = supabase.table("faucet_data").select("*").execute().data or []
    network_faucets = [{"network": r["network"], "faucets": r["faucets"]} for r in faucet_rows]
    total_faucets   = meta.get("total_faucets") or sum(r["faucets"] for r in network_faucets)

    # ── user_data ─────────────────────────────────────────────────────────────
    user_rows = supabase.table("user_data").select("*").order("date", desc=False).execute().data or []
    users_chart        = [{"date": r["date"], "newUsers": r["new_users"], "cumulativeUsers": r["cumulative_users"]} for r in user_rows]
    total_unique_users = meta.get("total_unique_users") or (user_rows[-1]["cumulative_users"] if user_rows else 0)

    # ── claim_data ────────────────────────────────────────────────────────────
    claim_rows = supabase.table("claim_data").select("*").order("latest_claim_time", desc=True).execute().data or []
    if not claim_rows and not meta:
        return None

    total_claims       = meta.get("total_claims")       or sum(r["claims"] for r in claim_rows)
    total_transactions = meta.get("total_transactions") or sum(r.get("total_transactions", r["claims"]) for r in claim_rows)

    faucet_rankings = [
        {
            "rank":            r.get("rank") or i + 1,
            "faucetAddress":   r["faucet_address"],
            "faucetName":      r["faucet_name"],
            "network":         r["network"],
            "chainId":         r.get("chain_id") or 0,
            "totalClaims":     r["claims"],
            "latestClaimTime": r["latest_claim_time"],
        }
        for i, r in enumerate(claim_rows)
    ]

    # ── network_transactions — prefer network_tx_data, fall back to claim_data 
    net_tx_rows = supabase.table("network_tx_data").select("*").execute().data or []
    if net_tx_rows:
        network_transactions = [
            {
                "name":              r["network"],
                "chainId":           r.get("chain_id") or 0,
                "totalTransactions": r["total_transactions"],
                "color":             r.get("color") or NETWORK_COLORS.get(r["network"], "#888888"),
            }
            for r in net_tx_rows
        ]
    else:
        # Fallback: aggregate from claim_data
        network_tx_map: Dict[str, int] = {}
        for r in claim_rows:
            net = r["network"]
            network_tx_map[net] = network_tx_map.get(net, 0) + r.get("total_transactions", r["claims"])
        for nf in network_faucets:
            network_tx_map.setdefault(nf["network"], 0)
        network_transactions = [
            {
                "name":              net,
                "chainId":           next((cid for cid, cfg in CHAIN_CONFIGS.items() if cfg["name"] == net), 0),
                "totalTransactions": tx_count,
                "color":             NETWORK_COLORS.get(net, "#888888"),
            }
            for net, tx_count in network_tx_map.items()
        ]

    # ── Pie data ──────────────────────────────────────────────────────────────
    sorted_by_claims = sorted(claim_rows, key=lambda r: r["claims"], reverse=True)
    pie = [
        {
            "name":          r["faucet_name"],
            "value":         r["claims"],
            "faucetAddress": r["faucet_address"],
            "network":       r["network"],
        }
        for r in sorted_by_claims[:10]
    ]
    others_count = sum(r["claims"] for r in sorted_by_claims[10:])
    if others_count > 0:
        pie.append({
            "name":          f"Others ({len(sorted_by_claims) - 10})",
            "value":         others_count,
            "faucetAddress": "others",
            "network":       "",
        })

    last_updated = meta.get("last_updated") or datetime.utcnow().isoformat()

    return {
        "total_claims":         total_claims,
        "total_unique_users":   total_unique_users,
        "total_faucets":        total_faucets,
        "total_transactions":   total_transactions,
        "claims_pie_data":      pie,
        "faucet_rankings":      faucet_rankings,
        "users_chart":          users_chart,
        "network_transactions": network_transactions,
        "network_faucets":      network_faucets,
        "last_updated":         last_updated,
    }


# ====================== ROUTES ======================

@app.get("/api/dashboard", response_model=DashboardResponse)
async def get_dashboard():
    """Serve dashboard data from Supabase. Falls back to in-memory cache."""
    if supabase:
        try:
            data = load_from_supabase()
            if data:
                return data
        except Exception as e:
            print(f"⚠️  Supabase read failed, falling back to in-memory: {e}")
    return dashboard_data


@app.get("/api/network/{chain_id}/faucets")
async def get_network_faucets(
    chain_id:     int,
    active_only:  bool          = Query(False),
    factory_type: Optional[str] = Query(None),
    search:       Optional[str] = Query(None),
    page:         int           = Query(1,  ge=1),
    per_page:     int           = Query(50, ge=1, le=200),
):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        q = supabase.table("network_faucets").select("*").eq("chain_id", chain_id)
        if active_only:
            q = q.eq("is_claim_active", True)
        if factory_type:
            q = q.eq("factory_type", factory_type)
        rows = q.order("start_time", desc=True).execute().data or []
        if search:
            s = search.strip().lower()
            rows = [r for r in rows if s in (r.get("faucet_name") or "").lower() or s in (r.get("token_symbol") or "").lower() or s in (r.get("faucet_address") or "").lower()]
        total = len(rows)
        start = (page - 1) * per_page
        return {"chain_id": chain_id, "network_name": CHAIN_CONFIGS.get(chain_id, {}).get("name", str(chain_id)), "total": total, "page": page, "per_page": per_page, "faucets": rows[start: start + per_page]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/faucet/{faucet_address}")
async def get_faucet_detail(faucet_address: str):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        rows = supabase.table("faucet_details").select("*").eq("faucet_address", faucet_address.lower()).limit(1).execute().data
        if not rows:
            raise HTTPException(status_code=404, detail=f"Faucet {faucet_address} not found.")
        return rows[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/faucets")
async def get_all_faucets(
    active_only:  bool          = Query(False),
    factory_type: Optional[str] = Query(None),
    search:       Optional[str] = Query(None),
    page:         int           = Query(1,  ge=1),
    per_page:     int           = Query(50, ge=1, le=200),
):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        q = supabase.table("network_faucets").select("*")
        if active_only:
            q = q.eq("is_claim_active", True)
        if factory_type:
            q = q.eq("factory_type", factory_type)
        rows = q.order("start_time", desc=True).execute().data or []
        if search:
            s = search.strip().lower()
            rows = [r for r in rows if s in (r.get("faucet_name") or "").lower() or s in (r.get("token_symbol") or "").lower() or s in (r.get("faucet_address") or "").lower()]
        total = len(rows)
        start = (page - 1) * per_page
        return {"total": total, "page": page, "per_page": per_page, "faucets": rows[start: start + per_page]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/network/{chain_id}/faucets/refresh")
async def refresh_network_endpoint(chain_id: int, background_tasks: BackgroundTasks):
    if chain_id not in CHAIN_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Chain {chain_id} not supported")
    background_tasks.add_task(refresh_network_faucets)
    return {"status": "refresh started", "chain_id": chain_id}


@app.get("/api/refresh")
async def manual_refresh():
    """
    Frontend-triggered refresh. Runs BOTH jobs and awaits completion so
    Supabase is fully updated before this endpoint returns — the frontend
    can then immediately re-query Supabase for fresh data.
    """
    print("\U0001f5b1\ufe0f  [manual_refresh] triggered by frontend")
    await asyncio.gather(
        refresh_all_data(),
        refresh_network_faucets(),
    )
    return {
        "status":       "complete",
        "last_updated": dashboard_data.get("last_updated"),
    }


# ====================== STARTUP ======================

@app.on_event("startup")
async def startup():
    global dashboard_data
    print("🚀 [Startup] API is coming online...")
    
    if supabase:
        try:
            # 1. Load whatever we have in the DB immediately so the UI isn't empty
            cached = load_from_supabase()
            if cached:
                dashboard_data = cached
                print("✅ [Startup] Loaded initial data from Supabase")
        except Exception as e:
            print(f"⚠️ [Startup] Supabase cache empty or failed: {e}")

    # 2. DO NOT 'await' these. Create them as background tasks.
    # This allows the API to return "Ready" to Render in milliseconds.
    asyncio.create_task(refresh_all_data())
    asyncio.create_task(refresh_network_faucets())


# ====================== RENDER.COM COMPATIBLE RUN ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    print(f"🚀 Starting FaucetDrop API on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
