"""ASX 200 symbols configuration for SCIZOR Data Farmer."""

# Top ASX 200 symbols for initial data collection
ASX_200_SYMBOLS = [
    # Top 10 by market cap
    "CBA.AX",   # Commonwealth Bank
    "BHP.AX",   # BHP Group
    "CSL.AX",   # CSL Limited
    "ANZ.AX",   # ANZ Banking Group
    "WBC.AX",   # Westpac Banking
    "NAB.AX",   # National Australia Bank
    "WES.AX",   # Wesfarmers
    "MQG.AX",   # Macquarie Group
    "TLS.AX",   # Telstra
    "WOW.AX",   # Woolworths Group
    
    # Additional major stocks
    "RIO.AX",   # Rio Tinto
    "FMG.AX",   # Fortescue Metals
    "WDS.AX",   # Woodside Energy
    "TCL.AX",   # Transurban Group
    "COL.AX",   # Coles Group
    "STO.AX",   # Santos
    "QBE.AX",   # QBE Insurance
    "REA.AX",   # REA Group
    "JHX.AX",   # James Hardie
    "ALL.AX",   # Aristocrat Leisure
    
    # Tech and growth stocks
    "XRO.AX",   # Xero
    "WTC.AX",   # WiseTech Global
    "CAR.AX",   # Carsales.com
    "SEK.AX",   # Seek Limited
    "APT.AX",   # Afterpay (if still listed)
    
    # Banks and financials
    "BOQ.AX",   # Bank of Queensland
    "BEN.AX",   # Bendigo Bank
    "SUN.AX",   # Suncorp Group
    "IAG.AX",   # Insurance Australia
    "AMP.AX",   # AMP Limited
    
    # Resources and mining
    "NCM.AX",   # Newcrest Mining
    "S32.AX",   # South32
    "OZL.AX",   # OZ Minerals
    "IGO.AX",   # IGO Limited
    "MIN.AX",   # Mineral Resources
    
    # Healthcare and biotech
    "COH.AX",   # Cochlear
    "RMD.AX",   # ResMed
    "SHL.AX",   # Sonic Healthcare
    "RHC.AX",   # Ramsay Health Care
    "PME.AX",   # Pro Medicus
    
    # REITs
    "SCG.AX",   # Scentre Group
    "GMG.AX",   # Goodman Group
    "MGR.AX",   # Mirvac Group
    "LLC.AX",   # Lendlease Group
    "CHC.AX",   # Charter Hall Group
]

# Symbol categories for organized data collection
SYMBOL_CATEGORIES = {
    "banks": ["CBA.AX", "ANZ.AX", "WBC.AX", "NAB.AX", "BOQ.AX", "BEN.AX"],
    "mining": ["BHP.AX", "RIO.AX", "FMG.AX", "NCM.AX", "S32.AX", "OZL.AX"],
    "energy": ["WDS.AX", "STO.AX", "ORG.AX"],
    "retail": ["WES.AX", "WOW.AX", "COL.AX", "JBH.AX"],
    "tech": ["XRO.AX", "WTC.AX", "CAR.AX", "SEK.AX", "TNE.AX"],
    "healthcare": ["CSL.AX", "COH.AX", "RMD.AX", "SHL.AX", "RHC.AX"],
    "reits": ["SCG.AX", "GMG.AX", "MGR.AX", "LLC.AX", "CHC.AX"],
    "utilities": ["TLS.AX", "TCL.AX", "APA.AX"],
    "industrials": ["JHX.AX", "ALL.AX", "REA.AX", "QBE.AX"]
}

# Market hours for ASX (AEST/AEDT)
ASX_MARKET_HOURS = {
    "open": "10:00",      # 10:00 AM AEST/AEDT
    "close": "16:00",     # 4:00 PM AEST/AEDT
    "timezone": "Australia/Sydney"
}

# Data collection priorities
PRIORITY_SYMBOLS = [
    "CBA.AX", "BHP.AX", "CSL.AX", "ANZ.AX", "WBC.AX", 
    "NAB.AX", "WES.AX", "MQG.AX", "TLS.AX", "WOW.AX"
]

def get_symbols_by_category(category: str = None):
    """Get symbols by category or all symbols."""
    if category and category in SYMBOL_CATEGORIES:
        return SYMBOL_CATEGORIES[category]
    return ASX_200_SYMBOLS[:50]  # Return first 50 symbols for initial setup
