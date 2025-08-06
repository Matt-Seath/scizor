#!/usr/bin/env python3
"""
Populate SCIZOR symbols table with ASX200 stocks, popular NASDAQ stocks, and ASX ETFs
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.database.connection import init_db, AsyncSessionLocal
from shared.database.models import Symbol, SecurityType
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ASX 200 Symbols (Complete list with market cap and priority)
ASX_200_SYMBOLS = [
    # ASX Top 20 (Tier 1 - Most Liquid)
    {"symbol": "CBA", "name": "Commonwealth Bank of Australia", "sector": "Financials", "market_cap": "Large", "priority": 1},
    {"symbol": "BHP", "name": "BHP Group Ltd", "sector": "Materials", "market_cap": "Large", "priority": 2},
    {"symbol": "CSL", "name": "CSL Ltd", "sector": "Health Care", "market_cap": "Large", "priority": 3},
    {"symbol": "ANZ", "name": "Australia and New Zealand Banking Group Ltd", "sector": "Financials", "market_cap": "Large", "priority": 4},
    {"symbol": "WBC", "name": "Westpac Banking Corp", "sector": "Financials", "market_cap": "Large", "priority": 5},
    {"symbol": "NAB", "name": "National Australia Bank Ltd", "sector": "Financials", "market_cap": "Large", "priority": 6},
    {"symbol": "WES", "name": "Wesfarmers Ltd", "sector": "Consumer Staples", "market_cap": "Large", "priority": 7},
    {"symbol": "MQG", "name": "Macquarie Group Ltd", "sector": "Financials", "market_cap": "Large", "priority": 8},
    {"symbol": "TLS", "name": "Telstra Group Ltd", "sector": "Communication Services", "market_cap": "Large", "priority": 9},
    {"symbol": "WOW", "name": "Woolworths Group Ltd", "sector": "Consumer Staples", "market_cap": "Large", "priority": 10},
    {"symbol": "FMG", "name": "Fortescue Ltd", "sector": "Materials", "market_cap": "Large", "priority": 11},
    {"symbol": "RIO", "name": "Rio Tinto Ltd", "sector": "Materials", "market_cap": "Large", "priority": 12},
    {"symbol": "TCL", "name": "Transurban Group", "sector": "Industrials", "market_cap": "Large", "priority": 13},
    {"symbol": "COL", "name": "Coles Group Ltd", "sector": "Consumer Staples", "market_cap": "Large", "priority": 14},
    {"symbol": "WDS", "name": "Woodside Energy Group Ltd", "sector": "Energy", "market_cap": "Large", "priority": 15},
    {"symbol": "STO", "name": "Santos Ltd", "sector": "Energy", "market_cap": "Large", "priority": 16},
    {"symbol": "ALL", "name": "Aristocrat Leisure Ltd", "sector": "Consumer Discretionary", "market_cap": "Large", "priority": 17},
    {"symbol": "XRO", "name": "Xero Ltd", "sector": "Technology", "market_cap": "Large", "priority": 18},
    {"symbol": "REA", "name": "REA Group Ltd", "sector": "Communication Services", "market_cap": "Large", "priority": 19},
    {"symbol": "QAN", "name": "Qantas Airways Ltd", "sector": "Industrials", "market_cap": "Large", "priority": 20},
    
    # ASX 21-50 (Tier 2)
    {"symbol": "GMG", "name": "Goodman Group", "sector": "Real Estate", "market_cap": "Large", "priority": 21},
    {"symbol": "JHX", "name": "James Hardie Industries plc", "sector": "Materials", "market_cap": "Large", "priority": 22},
    {"symbol": "IAG", "name": "Insurance Australia Group Ltd", "sector": "Financials", "market_cap": "Large", "priority": 23},
    {"symbol": "CPU", "name": "Computershare Ltd", "sector": "Technology", "market_cap": "Large", "priority": 24},
    {"symbol": "WOR", "name": "WorleyParsons Ltd", "sector": "Energy", "market_cap": "Large", "priority": 25},
    {"symbol": "ALX", "name": "Atlas Arteria", "sector": "Industrials", "market_cap": "Large", "priority": 26},
    {"symbol": "NCM", "name": "Newcrest Mining Ltd", "sector": "Materials", "market_cap": "Large", "priority": 27},
    {"symbol": "MIN", "name": "Mineral Resources Ltd", "sector": "Materials", "market_cap": "Large", "priority": 28},
    {"symbol": "EDV", "name": "Endeavour Group Ltd", "sector": "Consumer Staples", "market_cap": "Large", "priority": 29},
    {"symbol": "COH", "name": "Cochlear Ltd", "sector": "Health Care", "market_cap": "Large", "priority": 30},
    {"symbol": "AZJ", "name": "Aurizon Holdings Ltd", "sector": "Industrials", "market_cap": "Large", "priority": 31},
    {"symbol": "QBE", "name": "QBE Insurance Group Ltd", "sector": "Financials", "market_cap": "Large", "priority": 32},
    {"symbol": "APA", "name": "APA Group", "sector": "Utilities", "market_cap": "Large", "priority": 33},
    {"symbol": "ASX", "name": "ASX Ltd", "sector": "Financials", "market_cap": "Large", "priority": 34},
    {"symbol": "AGL", "name": "AGL Energy Ltd", "sector": "Utilities", "market_cap": "Large", "priority": 35},
    {"symbol": "ORG", "name": "Origin Energy Ltd", "sector": "Utilities", "market_cap": "Large", "priority": 36},
    {"symbol": "ALD", "name": "Ampol Ltd", "sector": "Energy", "market_cap": "Large", "priority": 37},
    {"symbol": "TAH", "name": "Tabcorp Holdings Ltd", "sector": "Consumer Discretionary", "market_cap": "Large", "priority": 38},
    {"symbol": "CAR", "name": "CAR Group Ltd", "sector": "Communication Services", "market_cap": "Large", "priority": 39},
    {"symbol": "CWN", "name": "Crown Resorts Ltd", "sector": "Consumer Discretionary", "market_cap": "Mid", "priority": 40},
    {"symbol": "IPL", "name": "Incitec Pivot Ltd", "sector": "Materials", "market_cap": "Mid", "priority": 41},
    {"symbol": "LLC", "name": "Lendlease Corp Ltd", "sector": "Real Estate", "market_cap": "Mid", "priority": 42},
    {"symbol": "CCL", "name": "Coca-Cola Amatil Ltd", "sector": "Consumer Staples", "market_cap": "Mid", "priority": 43},
    {"symbol": "BSL", "name": "BlueScope Steel Ltd", "sector": "Materials", "market_cap": "Mid", "priority": 44},
    {"symbol": "AMP", "name": "AMP Ltd", "sector": "Financials", "market_cap": "Mid", "priority": 45},
    {"symbol": "BAP", "name": "Bapcor Ltd", "sector": "Consumer Discretionary", "market_cap": "Mid", "priority": 46},
    {"symbol": "BXB", "name": "Brambles Ltd", "sector": "Industrials", "market_cap": "Mid", "priority": 47},
    {"symbol": "CHC", "name": "Charter Hall Group", "sector": "Real Estate", "market_cap": "Mid", "priority": 48},
    {"symbol": "DEG", "name": "De Grey Mining Ltd", "sector": "Materials", "market_cap": "Mid", "priority": 49},
    {"symbol": "DXS", "name": "Dexus", "sector": "Real Estate", "market_cap": "Mid", "priority": 50},
    
    # ASX 51-100 (Tier 3)
    {"symbol": "S32", "name": "South32 Ltd", "sector": "Materials", "market_cap": "Mid", "priority": 51},
    {"symbol": "SHL", "name": "Sonic Healthcare Ltd", "sector": "Health Care", "market_cap": "Mid", "priority": 52},
    {"symbol": "RMD", "name": "ResMed Inc", "sector": "Health Care", "market_cap": "Mid", "priority": 53},
    {"symbol": "WTC", "name": "WiseTech Global Ltd", "sector": "Technology", "market_cap": "Mid", "priority": 54},
    {"symbol": "EVN", "name": "Evolution Mining Ltd", "sector": "Materials", "market_cap": "Mid", "priority": 55},
    {"symbol": "ILU", "name": "Iluka Resources Ltd", "sector": "Materials", "market_cap": "Mid", "priority": 56},
    {"symbol": "BOQ", "name": "Bank of Queensland Ltd", "sector": "Financials", "market_cap": "Mid", "priority": 57},
    {"symbol": "BEN", "name": "Bendigo and Adelaide Bank Ltd", "sector": "Financials", "market_cap": "Mid", "priority": 58},
    {"symbol": "IGO", "name": "IGO Ltd", "sector": "Materials", "market_cap": "Mid", "priority": 59},
    {"symbol": "OZL", "name": "Oz Minerals Ltd", "sector": "Materials", "market_cap": "Mid", "priority": 60},
    {"symbol": "PME", "name": "Pro Medicus Ltd", "sector": "Health Care", "market_cap": "Mid", "priority": 61},
    {"symbol": "RHC", "name": "Ramsay Health Care Ltd", "sector": "Health Care", "market_cap": "Mid", "priority": 62},
    {"symbol": "SEK", "name": "Seek Ltd", "sector": "Communication Services", "market_cap": "Mid", "priority": 63},
    {"symbol": "TPG", "name": "TPG Telecom Ltd", "sector": "Communication Services", "market_cap": "Mid", "priority": 64},
    {"symbol": "NXT", "name": "NEXTDC Ltd", "sector": "Technology", "market_cap": "Mid", "priority": 65},
    {"symbol": "DMP", "name": "Domino's Pizza Enterprises Ltd", "sector": "Consumer Discretionary", "market_cap": "Mid", "priority": 66},
    {"symbol": "TWE", "name": "Treasury Wine Estates Ltd", "sector": "Consumer Staples", "market_cap": "Mid", "priority": 67},
    {"symbol": "SYD", "name": "Sydney Airport", "sector": "Industrials", "market_cap": "Mid", "priority": 68},
    {"symbol": "MEL", "name": "Melbourne Airport", "sector": "Industrials", "market_cap": "Mid", "priority": 69},
    {"symbol": "SCG", "name": "Scentre Group", "sector": "Real Estate"},
    {"symbol": "URW", "name": "Unibail-Rodamco-Westfield", "sector": "Real Estate"},
    {"symbol": "VCX", "name": "Vicinity Centres", "sector": "Real Estate"},
    {"symbol": "ALU", "name": "Altium Ltd", "sector": "Technology"},
    {"symbol": "APT", "name": "Afterpay Ltd", "sector": "Technology"},
    {"symbol": "ZIP", "name": "Zip Co Ltd", "sector": "Technology"},
    {"symbol": "IFL", "name": "IOOF Holdings Ltd", "sector": "Financials"},
    {"symbol": "HVN", "name": "Harvey Norman Holdings Ltd", "sector": "Consumer Discretionary"},
    {"symbol": "JBH", "name": "JB Hi-Fi Ltd", "sector": "Consumer Discretionary"},
    {"symbol": "SUL", "name": "Super Retail Group Ltd", "sector": "Consumer Discretionary"},
    {"symbol": "FLT", "name": "Flight Centre Travel Group Ltd", "sector": "Consumer Discretionary"},
    
    # ASX 101-150 (Tier 4)
    {"symbol": "NEC", "name": "Nine Entertainment Co Holdings Ltd", "sector": "Communication Services"},
    {"symbol": "OSH", "name": "Oil Search Ltd", "sector": "Energy"},
    {"symbol": "WHC", "name": "Whitehaven Coal Ltd", "sector": "Energy"},
    {"symbol": "NHC", "name": "New Hope Corp Ltd", "sector": "Energy"},
    {"symbol": "YAL", "name": "Yancoal Australia Ltd", "sector": "Energy"},
    {"symbol": "AQZ", "name": "Allegiance Coal Ltd", "sector": "Energy"},
    {"symbol": "CTX", "name": "Caltex Australia Ltd", "sector": "Energy"},
    {"symbol": "ORE", "name": "Orocobre Ltd", "sector": "Materials"},
    {"symbol": "PLS", "name": "Pilbara Minerals Ltd", "sector": "Materials"},
    {"symbol": "LYC", "name": "Lynas Rare Earths Ltd", "sector": "Materials"},
    {"symbol": "AVZ", "name": "AVZ Minerals Ltd", "sector": "Materials"},
    {"symbol": "TMZ", "name": "Thomson Resources Ltd", "sector": "Materials"},
    {"symbol": "GXY", "name": "Galaxy Resources Ltd", "sector": "Materials"},
    {"symbol": "LIT", "name": "Lithium Australia NL", "sector": "Materials"},
    {"symbol": "AKE", "name": "Allkem Ltd", "sector": "Materials"},
    {"symbol": "LTR", "name": "Liontown Resources Ltd", "sector": "Materials"},
    {"symbol": "CXO", "name": "Core Lithium Ltd", "sector": "Materials"},
    {"symbol": "SYR", "name": "Syrah Resources Ltd", "sector": "Materials"},
    {"symbol": "TMT", "name": "Technology Metals Australia Ltd", "sector": "Materials"},
    {"symbol": "CSR", "name": "CSR Ltd", "sector": "Materials"},
    {"symbol": "ABC", "name": "Adelaide Brighton Ltd", "sector": "Materials"},
    {"symbol": "BLD", "name": "Boral Ltd", "sector": "Materials"},
    {"symbol": "FBU", "name": "Fletcher Building Ltd", "sector": "Materials"},
    {"symbol": "JHG", "name": "Janus Henderson Group plc", "sector": "Financials"},
    {"symbol": "PPT", "name": "Perpetual Ltd", "sector": "Financials"},
    {"symbol": "PTM", "name": "Platinum Asset Management Ltd", "sector": "Financials"},
    {"symbol": "MFG", "name": "Magellan Financial Group Ltd", "sector": "Financials"},
    
    # ASX 151-200 (Tier 5)
    {"symbol": "RWC", "name": "Reliance Worldwide Corp Ltd", "sector": "Industrials"},
    {"symbol": "TNE", "name": "Technology One Ltd", "sector": "Technology"},
    {"symbol": "ING", "name": "Inghams Group Ltd", "sector": "Consumer Staples"},
    {"symbol": "A2M", "name": "The a2 Milk Company Ltd", "sector": "Consumer Staples"},
    {"symbol": "BAL", "name": "Bellamy's Australia Ltd", "sector": "Consumer Staples"},
    {"symbol": "BGA", "name": "Bega Cheese Ltd", "sector": "Consumer Staples"},
    {"symbol": "CCX", "name": "City Chic Collective Ltd", "sector": "Consumer Discretionary"},
    {"symbol": "KGN", "name": "Kogan.com Ltd", "sector": "Consumer Discretionary"},
    {"symbol": "PMV", "name": "Premier Investments Ltd", "sector": "Consumer Discretionary"},
    {"symbol": "SRV", "name": "Service Stream Ltd", "sector": "Industrials"},
    {"symbol": "NAN", "name": "Nanosonics Ltd", "sector": "Health Care"},
    {"symbol": "IVC", "name": "InvoCare Ltd", "sector": "Consumer Discretionary"},
    {"symbol": "SIG", "name": "Sigma Healthcare Ltd", "sector": "Health Care"},
    {"symbol": "API", "name": "Australian Pharmaceutical Industries Ltd", "sector": "Health Care"},
    {"symbol": "MYR", "name": "Myer Holdings Ltd", "sector": "Consumer Discretionary"},
    {"symbol": "KMD", "name": "KMD Brands Ltd", "sector": "Consumer Discretionary"},
    {"symbol": "BBN", "name": "Baby Bunting Group Ltd", "sector": "Consumer Discretionary"},
    {"symbol": "LOV", "name": "Lovisa Holdings Ltd", "sector": "Consumer Discretionary"},
    {"symbol": "JIN", "name": "Jumbo Interactive Ltd", "sector": "Consumer Discretionary"},
    {"symbol": "PNI", "name": "Pinnacle Investment Management Group Ltd", "sector": "Financials"},
    {"symbol": "HUB", "name": "Hub24 Ltd", "sector": "Financials"},
    {"symbol": "NMT", "name": "Neometals Ltd", "sector": "Materials"},
    {"symbol": "PEN", "name": "Peninsula Energy Ltd", "sector": "Energy"},
    {"symbol": "AGE", "name": "Alligator Energy Ltd", "sector": "Energy"},
    {"symbol": "BOE", "name": "Boss Energy Ltd", "sector": "Energy"},
    {"symbol": "BMN", "name": "Bannerman Energy Ltd", "sector": "Energy"},
    {"symbol": "DYL", "name": "Deep Yellow Ltd", "sector": "Energy"},
    {"symbol": "LOT", "name": "Lotus Resources Ltd", "sector": "Energy"},
    {"symbol": "PDN", "name": "Paladin Energy Ltd", "sector": "Energy"},
    {"symbol": "VMY", "name": "Vimy Resources Ltd", "sector": "Energy"},
    {"symbol": "ERA", "name": "Energy Resources of Australia Ltd", "sector": "Energy"},
    {"symbol": "GTR", "name": "GTI Resources Ltd", "sector": "Materials"},
    {"symbol": "TMR", "name": "Tempus Resources Ltd", "sector": "Materials"},
    {"symbol": "LRS", "name": "Latin Resources Ltd", "sector": "Materials"},
    {"symbol": "AVL", "name": "Australian Vanadium Ltd", "sector": "Materials"},
    {"symbol": "CXZ", "name": "Connexion Telematics Ltd", "sector": "Technology"},
    {"symbol": "TNT", "name": "Tesserent Ltd", "sector": "Technology"},
    {"symbol": "MNY", "name": "Money3 Corp Ltd", "sector": "Financials"},
    {"symbol": "CLH", "name": "Collection House Ltd", "sector": "Financials"},
    {"symbol": "CCP", "name": "Credit Corp Group Ltd", "sector": "Financials"},
    {"symbol": "LAM", "name": "Lam Research Corp", "sector": "Technology"},
    {"symbol": "FFI", "name": "FFI Holdings Ltd", "sector": "Industrials"},
    {"symbol": "ELD", "name": "Elders Ltd", "sector": "Industrials"},
    {"symbol": "GNC", "name": "Graincorp Ltd", "sector": "Consumer Staples"},
    {"symbol": "NUF", "name": "Nufarm Ltd", "sector": "Materials"}
]

# Popular ASX ETFs (Exchange Traded Funds)
ASX_ETF_SYMBOLS = [
    # Vanguard ETFs (Most Popular)
    {"symbol": "VAS", "name": "Vanguard Australian Shares Index ETF", "sector": "ETF", "market_cap": "Large", "priority": 301},
    {"symbol": "VGS", "name": "Vanguard MSCI Index International Shares ETF", "sector": "ETF", "market_cap": "Large", "priority": 302},
    {"symbol": "VTS", "name": "Vanguard US Total Market Shares Index ETF", "sector": "ETF", "market_cap": "Large", "priority": 303},
    {"symbol": "VEU", "name": "Vanguard All-World ex-US Shares Index ETF", "sector": "ETF", "market_cap": "Large", "priority": 304},
    {"symbol": "VAP", "name": "Vanguard Australian Property Securities Index ETF", "sector": "ETF", "market_cap": "Mid", "priority": 305},
    {"symbol": "VGB", "name": "Vanguard Australian Government Bond Index ETF", "sector": "ETF", "market_cap": "Mid", "priority": 306},
    {"symbol": "VCF", "name": "Vanguard International Credit Securities Index ETF", "sector": "ETF", "market_cap": "Mid", "priority": 307},
    {"symbol": "VDHG", "name": "Vanguard Diversified High Growth Index ETF", "sector": "ETF", "market_cap": "Large", "priority": 308},
    {"symbol": "VDGR", "name": "Vanguard Diversified Growth Index ETF", "sector": "ETF", "market_cap": "Large", "priority": 309},
    {"symbol": "VDBA", "name": "Vanguard Diversified Balanced Index ETF", "sector": "ETF", "market_cap": "Mid", "priority": 310},
    {"symbol": "VDCO", "name": "Vanguard Diversified Conservative Index ETF", "sector": "ETF", "market_cap": "Mid", "priority": 311},
    {"symbol": "VGE", "name": "Vanguard FTSE Emerging Markets Shares ETF", "sector": "ETF", "market_cap": "Mid", "priority": 312},
    
    # iShares ETFs
    {"symbol": "IVV", "name": "iShares Core S&P 500 ETF", "sector": "ETF", "market_cap": "Large", "priority": 313},
    {"symbol": "IOZ", "name": "iShares Core S&P/ASX 200 ETF", "sector": "ETF", "market_cap": "Large", "priority": 314},
    {"symbol": "IJH", "name": "iShares Core S&P Mid-Cap ETF", "sector": "ETF", "market_cap": "Mid", "priority": 315},
    {"symbol": "IJR", "name": "iShares Core S&P Small-Cap ETF", "sector": "ETF", "market_cap": "Mid", "priority": 316},
    {"symbol": "IEU", "name": "iShares Core MSCI Europe IMI Index ETF", "sector": "ETF", "market_cap": "Mid", "priority": 317},
    {"symbol": "IAA", "name": "iShares Core Composite Bond ETF", "sector": "ETF", "market_cap": "Mid", "priority": 318},
    {"symbol": "IEM", "name": "iShares MSCI Emerging Markets IMI Index ETF", "sector": "ETF", "market_cap": "Mid", "priority": 319},
    {"symbol": "IEMA", "name": "iShares MSCI Emerging Markets Asia ETF", "sector": "ETF", "market_cap": "Small", "priority": 320},
    
    # SPDR State Street ETFs
    {"symbol": "STW", "name": "SPDR S&P/ASX 200 Fund", "sector": "ETF", "market_cap": "Large", "priority": 321},
    {"symbol": "SFY", "name": "SPDR S&P/ASX 50 Fund", "sector": "ETF", "market_cap": "Large", "priority": 322},
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "sector": "ETF", "market_cap": "Large", "priority": 323},
    {"symbol": "SLF", "name": "SPDR S&P/ASX 200 Listed Property Fund", "sector": "ETF", "market_cap": "Mid", "priority": 324},
    
    # BetaShares ETFs
    {"symbol": "A200", "name": "BetaShares Australia 200 ETF", "sector": "ETF", "market_cap": "Large", "priority": 325},
    {"symbol": "NDQ", "name": "BetaShares NASDAQ 100 ETF", "sector": "ETF", "market_cap": "Large", "priority": 326},
    {"symbol": "BBOZ", "name": "BetaShares Strong Australian Dollar Hedge Fund", "sector": "ETF", "market_cap": "Small", "priority": 327},
    {"symbol": "BEAR", "name": "BetaShares Australian Equities Strong Bear Hedge Fund", "sector": "ETF", "market_cap": "Small", "priority": 328},
    {"symbol": "GEAR", "name": "BetaShares Geared Australian Equity Fund", "sector": "ETF", "market_cap": "Small", "priority": 329},
    {"symbol": "GOLD", "name": "BetaShares Gold Bullion ETF", "sector": "ETF", "market_cap": "Mid", "priority": 330},
    {"symbol": "CRYP", "name": "BetaShares Crypto Innovators ETF", "sector": "ETF", "market_cap": "Small", "priority": 331},
    {"symbol": "ASIA", "name": "BetaShares Asia Technology Tigers ETF", "sector": "ETF", "market_cap": "Mid", "priority": 332},
    {"symbol": "HACK", "name": "BetaShares Global Cybersecurity ETF", "sector": "ETF", "market_cap": "Small", "priority": 333},
    {"symbol": "RBTZ", "name": "BetaShares Global Robotics and Artificial Intelligence ETF", "sector": "ETF", "market_cap": "Small", "priority": 334},
    {"symbol": "DRUG", "name": "BetaShares Global Healthcare ETF", "sector": "ETF", "market_cap": "Small", "priority": 335},
    {"symbol": "FOOD", "name": "BetaShares Global Agriculture Companies ETF", "sector": "ETF", "market_cap": "Small", "priority": 336},
    {"symbol": "FUEL", "name": "BetaShares Global Energy Companies ETF", "sector": "ETF", "market_cap": "Small", "priority": 337},
    {"symbol": "TECH", "name": "BetaShares S&P/ASX Australian Technology ETF", "sector": "ETF", "market_cap": "Mid", "priority": 338},
    
    # VanEck ETFs
    {"symbol": "MVW", "name": "VanEck Vectors MSCI World ex Australia Quality ETF", "sector": "ETF", "market_cap": "Mid", "priority": 339},
    {"symbol": "MVA", "name": "VanEck Vectors MSCI Australian Small Companies Index ETF", "sector": "ETF", "market_cap": "Mid", "priority": 340},
    {"symbol": "QUAL", "name": "VanEck Vectors MSCI World ex Australia Quality ETF", "sector": "ETF", "market_cap": "Mid", "priority": 341},
    {"symbol": "MOAT", "name": "VanEck Vectors Morningstar Wide Moat ETF", "sector": "ETF", "market_cap": "Mid", "priority": 342},
    {"symbol": "GLDM", "name": "VanEck Vectors Gold Miners ETF", "sector": "ETF", "market_cap": "Mid", "priority": 343},
    
    # Magellan ETFs
    {"symbol": "MGE", "name": "Magellan Global Equities Fund", "sector": "ETF", "market_cap": "Large", "priority": 344},
    {"symbol": "MHH", "name": "Magellan High Conviction Fund", "sector": "ETF", "market_cap": "Mid", "priority": 345},
    
    # Russell Investments ETFs
    {"symbol": "RDV", "name": "Russell High Dividend Australian Shares ETF", "sector": "ETF", "market_cap": "Mid", "priority": 346},
    
    # ActiveX ETFs
    {"symbol": "ACDC", "name": "ActiveX Ardea Real Outcome Bond Fund", "sector": "ETF", "market_cap": "Small", "priority": 347},
    
    # Global X ETFs
    {"symbol": "ROBO", "name": "Global X Robotics & Artificial Intelligence ETF", "sector": "ETF", "market_cap": "Small", "priority": 348},
    {"symbol": "CLNE", "name": "Global X Clean Energy ETF", "sector": "ETF", "market_cap": "Small", "priority": 349},
    
    # Specialty and Sector ETFs
    {"symbol": "QFN", "name": "BetaShares S&P/ASX 200 Financials Sector ETF", "sector": "ETF", "market_cap": "Mid", "priority": 350},
    {"symbol": "QRE", "name": "BetaShares S&P/ASX 200 Resources Sector ETF", "sector": "ETF", "market_cap": "Mid", "priority": 351},
    {"symbol": "YMAX", "name": "BetaShares Australia Top 20 Equity Yield Maximiser Fund", "sector": "ETF", "market_cap": "Mid", "priority": 352}
]

# Popular NASDAQ Symbols (Top 100 most traded)
NASDAQ_SYMBOLS = [
    # FAANG + Mega Caps
    {"symbol": "AAPL", "name": "Apple Inc", "sector": "Technology"},
    {"symbol": "MSFT", "name": "Microsoft Corp", "sector": "Technology"},
    {"symbol": "GOOGL", "name": "Alphabet Inc Class A", "sector": "Communication Services"},
    {"symbol": "GOOG", "name": "Alphabet Inc Class C", "sector": "Communication Services"},
    {"symbol": "AMZN", "name": "Amazon.com Inc", "sector": "Consumer Discretionary"},
    {"symbol": "TSLA", "name": "Tesla Inc", "sector": "Consumer Discretionary"},
    {"symbol": "META", "name": "Meta Platforms Inc", "sector": "Communication Services"},
    {"symbol": "NVDA", "name": "NVIDIA Corp", "sector": "Technology"},
    {"symbol": "NFLX", "name": "Netflix Inc", "sector": "Communication Services"},
    
    # Other Major Tech
    {"symbol": "ADBE", "name": "Adobe Inc", "sector": "Technology"},
    {"symbol": "CRM", "name": "Salesforce Inc", "sector": "Technology"},
    {"symbol": "ORCL", "name": "Oracle Corp", "sector": "Technology"},
    {"symbol": "INTC", "name": "Intel Corp", "sector": "Technology"},
    {"symbol": "AMD", "name": "Advanced Micro Devices Inc", "sector": "Technology"},
    {"symbol": "CSCO", "name": "Cisco Systems Inc", "sector": "Technology"},
    {"symbol": "AVGO", "name": "Broadcom Inc", "sector": "Technology"},
    {"symbol": "QCOM", "name": "QUALCOMM Inc", "sector": "Technology"},
    {"symbol": "TXN", "name": "Texas Instruments Inc", "sector": "Technology"},
    {"symbol": "MU", "name": "Micron Technology Inc", "sector": "Technology"},
    {"symbol": "AMAT", "name": "Applied Materials Inc", "sector": "Technology"},
    
    # Software & Cloud
    {"symbol": "NOW", "name": "ServiceNow Inc", "sector": "Technology"},
    {"symbol": "SNOW", "name": "Snowflake Inc", "sector": "Technology"},
    {"symbol": "TEAM", "name": "Atlassian Corp", "sector": "Technology"},
    {"symbol": "WDAY", "name": "Workday Inc", "sector": "Technology"},
    {"symbol": "ZM", "name": "Zoom Video Communications Inc", "sector": "Technology"},
    {"symbol": "DOCU", "name": "DocuSign Inc", "sector": "Technology"},
    {"symbol": "SPLK", "name": "Splunk Inc", "sector": "Technology"},
    {"symbol": "OKTA", "name": "Okta Inc", "sector": "Technology"},
    {"symbol": "ZS", "name": "Zscaler Inc", "sector": "Technology"},
    {"symbol": "CRWD", "name": "CrowdStrike Holdings Inc", "sector": "Technology"},
    
    # Biotech & Healthcare
    {"symbol": "GILD", "name": "Gilead Sciences Inc", "sector": "Health Care"},
    {"symbol": "AMGN", "name": "Amgen Inc", "sector": "Health Care"},
    {"symbol": "BIIB", "name": "Biogen Inc", "sector": "Health Care"},
    {"symbol": "REGN", "name": "Regeneron Pharmaceuticals Inc", "sector": "Health Care"},
    {"symbol": "VRTX", "name": "Vertex Pharmaceuticals Inc", "sector": "Health Care"},
    {"symbol": "ILMN", "name": "Illumina Inc", "sector": "Health Care"},
    {"symbol": "MRNA", "name": "Moderna Inc", "sector": "Health Care"},
    {"symbol": "BNTX", "name": "BioNTech SE", "sector": "Health Care"},
    
    # E-commerce & Consumer
    {"symbol": "EBAY", "name": "eBay Inc", "sector": "Consumer Discretionary"},
    {"symbol": "PYPL", "name": "PayPal Holdings Inc", "sector": "Financials"},
    {"symbol": "SQ", "name": "Block Inc", "sector": "Financials"},
    {"symbol": "SHOP", "name": "Shopify Inc", "sector": "Technology"},
    {"symbol": "ROKU", "name": "Roku Inc", "sector": "Communication Services"},
    {"symbol": "SPOT", "name": "Spotify Technology SA", "sector": "Communication Services"},
    {"symbol": "UBER", "name": "Uber Technologies Inc", "sector": "Industrials"},
    {"symbol": "LYFT", "name": "Lyft Inc", "sector": "Industrials"},
    {"symbol": "DASH", "name": "DoorDash Inc", "sector": "Consumer Discretionary"},
    {"symbol": "ABNB", "name": "Airbnb Inc", "sector": "Consumer Discretionary"},
    
    # Semiconductors
    {"symbol": "LRCX", "name": "Lam Research Corp", "sector": "Technology"},
    {"symbol": "KLAC", "name": "KLA Corp", "sector": "Technology"},
    {"symbol": "MRVL", "name": "Marvell Technology Inc", "sector": "Technology"},
    {"symbol": "XLNX", "name": "Xilinx Inc", "sector": "Technology"},
    {"symbol": "MCHP", "name": "Microchip Technology Inc", "sector": "Technology"},
    {"symbol": "ADI", "name": "Analog Devices Inc", "sector": "Technology"},
    {"symbol": "SWKS", "name": "Skyworks Solutions Inc", "sector": "Technology"},
    
    # Growth Stocks
    {"symbol": "COST", "name": "Costco Wholesale Corp", "sector": "Consumer Staples"},
    {"symbol": "SBUX", "name": "Starbucks Corp", "sector": "Consumer Discretionary"},
    {"symbol": "LULU", "name": "Lululemon Athletica Inc", "sector": "Consumer Discretionary"},
    {"symbol": "PTON", "name": "Peloton Interactive Inc", "sector": "Consumer Discretionary"},
    {"symbol": "ZG", "name": "Zillow Group Inc", "sector": "Communication Services"},
    {"symbol": "DKNG", "name": "DraftKings Inc", "sector": "Consumer Discretionary"},
    {"symbol": "PENN", "name": "Penn Entertainment Inc", "sector": "Consumer Discretionary"},
    
    # Electric Vehicles & Clean Energy
    {"symbol": "NIO", "name": "NIO Inc", "sector": "Consumer Discretionary"},
    {"symbol": "XPEV", "name": "XPeng Inc", "sector": "Consumer Discretionary"},
    {"symbol": "LI", "name": "Li Auto Inc", "sector": "Consumer Discretionary"},
    {"symbol": "RIVN", "name": "Rivian Automotive Inc", "sector": "Consumer Discretionary"},
    {"symbol": "LCID", "name": "Lucid Group Inc", "sector": "Consumer Discretionary"},
    {"symbol": "ENPH", "name": "Enphase Energy Inc", "sector": "Technology"},
    {"symbol": "SEDG", "name": "SolarEdge Technologies Inc", "sector": "Technology"},
    
    # Communication & Media
    {"symbol": "CMCSA", "name": "Comcast Corp", "sector": "Communication Services"},
    {"symbol": "DISH", "name": "DISH Network Corp", "sector": "Communication Services"},
    {"symbol": "SIRI", "name": "Sirius XM Holdings Inc", "sector": "Communication Services"},
    {"symbol": "TWTR", "name": "Twitter Inc", "sector": "Communication Services"},
    {"symbol": "SNAP", "name": "Snap Inc", "sector": "Communication Services"},
    {"symbol": "PINS", "name": "Pinterest Inc", "sector": "Communication Services"},
    
    # Financials & Fintech
    {"symbol": "FISV", "name": "Fiserv Inc", "sector": "Financials"},
    {"symbol": "INTU", "name": "Intuit Inc", "sector": "Technology"},
    {"symbol": "ADSK", "name": "Autodesk Inc", "sector": "Technology"},
    {"symbol": "PAYX", "name": "Paychex Inc", "sector": "Financials"},
    {"symbol": "ADP", "name": "Automatic Data Processing Inc", "sector": "Financials"},
    
    # Gaming & Entertainment
    {"symbol": "EA", "name": "Electronic Arts Inc", "sector": "Communication Services"},
    {"symbol": "ATVI", "name": "Activision Blizzard Inc", "sector": "Communication Services"},
    {"symbol": "TTWO", "name": "Take-Two Interactive Software Inc", "sector": "Communication Services"},
    {"symbol": "RBLX", "name": "Roblox Corp", "sector": "Communication Services"},
    
    # Food & Beverages
    {"symbol": "PEP", "name": "PepsiCo Inc", "sector": "Consumer Staples"},
    {"symbol": "MDLZ", "name": "Mondelez International Inc", "sector": "Consumer Staples"},
    {"symbol": "KHC", "name": "The Kraft Heinz Co", "sector": "Consumer Staples"},
    
    # Retail
    {"symbol": "WBA", "name": "Walgreens Boots Alliance Inc", "sector": "Consumer Staples"},
    {"symbol": "DLTR", "name": "Dollar Tree Inc", "sector": "Consumer Discretionary"},
    {"symbol": "FAST", "name": "Fastenal Co", "sector": "Industrials"},
    
    # Airlines & Transportation  
    {"symbol": "AAL", "name": "American Airlines Group Inc", "sector": "Industrials"},
    {"symbol": "DAL", "name": "Delta Air Lines Inc", "sector": "Industrials"},
    {"symbol": "UAL", "name": "United Airlines Holdings Inc", "sector": "Industrials"},
    {"symbol": "LUV", "name": "Southwest Airlines Co", "sector": "Industrials"},
    
    # REITs & Real Estate
    {"symbol": "EQIX", "name": "Equinix Inc", "sector": "Real Estate"},
    {"symbol": "DLR", "name": "Digital Realty Trust Inc", "sector": "Real Estate"},
    {"symbol": "CCI", "name": "Crown Castle Inc", "sector": "Real Estate"},
    
    # Others
    {"symbol": "ISRG", "name": "Intuitive Surgical Inc", "sector": "Health Care"},
    {"symbol": "CSX", "name": "CSX Corp", "sector": "Industrials"},
    {"symbol": "PANW", "name": "Palo Alto Networks Inc", "sector": "Technology"},
    {"symbol": "FTNT", "name": "Fortinet Inc", "sector": "Technology"},
    {"symbol": "DXCM", "name": "DexCom Inc", "sector": "Health Care"},
    {"symbol": "ALGN", "name": "Align Technology Inc", "sector": "Health Care"},
    {"symbol": "BKNG", "name": "Booking Holdings Inc", "sector": "Consumer Discretionary"},
    {"symbol": "EXPD", "name": "Expeditors International of Washington Inc", "sector": "Industrials"}
]


async def populate_symbols():
    """Populate the symbols table with ASX200 and NASDAQ symbols."""
    
    logger.info("🚀 Starting symbol population...")
    
    # Initialize database
    await init_db()
    
    async with AsyncSessionLocal() as session:
        try:
            # Check existing symbols
            existing_result = await session.execute(select(Symbol))
            existing_symbols = {s.symbol for s in existing_result.scalars().all()}
            logger.info(f"📊 Found {len(existing_symbols)} existing symbols")
            
            total_added = 0
            total_skipped = 0
            
            # Process ASX symbols
            logger.info("📈 Processing ASX 200 symbols...")
            for symbol_data in ASX_200_SYMBOLS:
                if symbol_data["symbol"] not in existing_symbols:
                    new_symbol = Symbol(
                        symbol=symbol_data["symbol"],
                        company_name=symbol_data["name"],
                        exchange="ASX",
                        currency="AUD",
                        security_type=SecurityType.STOCK,
                        sector=symbol_data.get("sector", "Unknown"),
                        market_cap_category=symbol_data.get("market_cap", "Mid"),
                        local_symbol=f"{symbol_data['symbol']}.AX",  # IBKR format
                        active=True,
                        is_asx200=True,
                        priority=symbol_data.get("priority", 100),
                        min_tick=0.01,  # Standard ASX tick size
                        tradeable=True
                    )
                    session.add(new_symbol)
                    total_added += 1
                    logger.info(f"✨ Added ASX symbol: {symbol_data['symbol']} - {symbol_data['name']}")
                else:
                    total_skipped += 1
                    logger.info(f"⏭️  Skipped existing ASX symbol: {symbol_data['symbol']}")
            
            # Process NASDAQ symbols
            logger.info("📈 Processing NASDAQ symbols...")
            for symbol_data in NASDAQ_SYMBOLS:
                if symbol_data["symbol"] not in existing_symbols:
                    new_symbol = Symbol(
                        symbol=symbol_data["symbol"],
                        company_name=symbol_data["name"],
                        exchange="NASDAQ",
                        currency="USD",
                        security_type=SecurityType.STOCK,
                        sector=symbol_data.get("sector", "Unknown"),
                        market_cap_category=symbol_data.get("market_cap", "Large"),
                        local_symbol=symbol_data["symbol"],  # No suffix needed for NASDAQ
                        active=True,
                        is_asx200=False,
                        priority=symbol_data.get("priority", 200),  # Lower priority than ASX
                        min_tick=0.01,  # Standard US tick size
                        tradeable=True
                    )
                    session.add(new_symbol)
                    total_added += 1
                    logger.info(f"✨ Added NASDAQ symbol: {symbol_data['symbol']} - {symbol_data['name']}")
                else:
                    total_skipped += 1
                    logger.info(f"⏭️  Skipped existing NASDAQ symbol: {symbol_data['symbol']}")
            
            # Process ASX ETF symbols
            logger.info("💼 Processing ASX ETF symbols...")
            for symbol_data in ASX_ETF_SYMBOLS:
                if symbol_data["symbol"] not in existing_symbols:
                    new_symbol = Symbol(
                        symbol=symbol_data["symbol"],
                        company_name=symbol_data["name"],
                        exchange="ASX",
                        currency="AUD",
                        security_type=SecurityType.ETF,
                        sector=symbol_data.get("sector", "ETF"),
                        market_cap_category=symbol_data.get("market_cap", "Mid"),
                        local_symbol=f"{symbol_data['symbol']}.AX",  # IBKR format
                        active=True,
                        is_asx200=False,  # ETFs are separate from ASX200
                        priority=symbol_data.get("priority", 300),  # Lower priority than individual stocks
                        min_tick=0.01,  # Standard ASX tick size
                        tradeable=True
                    )
                    session.add(new_symbol)
                    total_added += 1
                    logger.info(f"✨ Added ASX ETF symbol: {symbol_data['symbol']} - {symbol_data['name']}")
                else:
                    total_skipped += 1
                    logger.info(f"⏭️  Skipped existing ASX ETF symbol: {symbol_data['symbol']}")
            
            # Commit all changes
            await session.commit()
            
            # Get final count
            final_result = await session.execute(select(Symbol))
            final_count = len(final_result.scalars().all())
            
            logger.info("🎉 Symbol population completed!")
            logger.info(f"📊 Summary:")
            logger.info(f"   • ASX 200 symbols: {len(ASX_200_SYMBOLS)}")
            logger.info(f"   • NASDAQ symbols: {len(NASDAQ_SYMBOLS)}")
            logger.info(f"   • ASX ETF symbols: {len(ASX_ETF_SYMBOLS)}")
            logger.info(f"   • Total symbols available: {len(ASX_200_SYMBOLS) + len(NASDAQ_SYMBOLS) + len(ASX_ETF_SYMBOLS)}")
            logger.info(f"   • New symbols added: {total_added}")
            logger.info(f"   • Existing symbols skipped: {total_skipped}")
            logger.info(f"   • Total symbols in database: {final_count}")
            
            return {
                "asx_symbols": len(ASX_200_SYMBOLS),
                "nasdaq_symbols": len(NASDAQ_SYMBOLS),
                "asx_etf_symbols": len(ASX_ETF_SYMBOLS),
                "total_available": len(ASX_200_SYMBOLS) + len(NASDAQ_SYMBOLS) + len(ASX_ETF_SYMBOLS),
                "added": total_added,
                "skipped": total_skipped,
                "final_count": final_count
            }
            
        except Exception as e:
            logger.error(f"❌ Error populating symbols: {e}")
            await session.rollback()
            raise


async def main():
    """Main execution function."""
    try:
        result = await populate_symbols()
        
        print("\n" + "="*60)
        print("🎯 SCIZOR SYMBOL POPULATION COMPLETE")
        print("="*60)
        print(f"📊 ASX 200 Symbols: {result['asx_symbols']}")
        print(f"💻 NASDAQ Symbols: {result['nasdaq_symbols']}")
        print(f"💼 ASX ETF Symbols: {result['asx_etf_symbols']}")
        print(f"🌎 Total Universe: {result['total_available']} symbols")
        print(f"✨ Newly Added: {result['added']}")
        print(f"💾 Total in Database: {result['final_count']}")
        print("="*60)
        print("✅ Ready for data collection configuration!")
        
    except Exception as e:
        logger.error(f"❌ Failed to populate symbols: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
