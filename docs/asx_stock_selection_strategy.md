# SCIZOR ASX Stock Selection Strategy
**Optimal 15-20 Stock Portfolio for IBKR Free-Tier**

**Created**: August 7, 2025  
**Purpose**: Define the optimal ASX stock selection for SCIZOR's free-tier IBKR strategy  
**Reference**: Implementation of `docs/ibkr_free_tier_strategy.md`

---

## 🎯 Selection Criteria

Based on the IBKR free-tier constraints and SCIZOR's trading objectives:

### **Primary Criteria (Must Have)**
- **Market Cap**: Top ASX 200 constituents (>$2B market cap)
- **Liquidity**: High daily trading volume (>$10M daily average)
- **Sector Diversification**: Balance across key ASX sectors
- **Data Availability**: Reliable IBKR data feed coverage
- **Volatility**: Sufficient price movement for profitable signals

### **Secondary Criteria (Preferred)**
- **ASX 20 Inclusion**: Priority for most liquid blue-chips
- **Options Availability**: For future strategy expansion
- **Dividend Stability**: Consistent dividend history
- **International Exposure**: Some global revenue exposure
- **Technical Patterns**: Strong trend characteristics

---

## 📊 Recommended 18-Stock Portfolio

### **Tier 1: Core Blue Chips (8 stocks)**
*Highest liquidity, lowest risk, ASX 20 constituents*

| **Symbol** | **Company** | **Sector** | **Market Cap** | **Rationale** |
|------------|-------------|-------------|----------------|---------------|
| **CBA** | Commonwealth Bank | Financials | $181.4B | Largest bank, highest liquidity, defensive |
| **BHP** | BHP Group | Materials | $142.5B | Mining giant, commodity exposure, global |
| **WBC** | Westpac Banking | Financials | $92.9B | Big 4 bank, high volume, yield |
| **CSL** | CSL Limited | Healthcare | $132.9B | Biotech leader, defensive growth |
| **ANZ** | ANZ Banking Group | Financials | $81.8B | Big 4 bank, regional exposure |
| **NAB** | National Australia Bank | Financials | $69.8B | Big 4 bank, business banking focus |
| **WOW** | Woolworths Group | Consumer Staples | $37.8B | Retail leader, defensive, stable |
| **WES** | Wesfarmers | Consumer Disc. | $37.6B | Diversified retail, Bunnings dominance |

**Total: 8/18 stocks (44%) - Provides market stability and liquidity foundation**

### **Tier 2: Large Cap Growth & Resources (6 stocks)**
*Strong growth potential, sector diversification*

| **Symbol** | **Company** | **Sector** | **Market Cap** | **Rationale** |
|------------|-------------|-------------|----------------|---------------|
| **RIO** | Rio Tinto | Materials | $35.7B | Iron ore/copper, global mining leader |
| **FMG** | Fortescue Metals | Materials | $70.8B | Iron ore specialist, high beta |
| **TLS** | Telstra Corporation | Communication | $37.2B | Telco leader, 5G infrastructure |
| **TCL** | Transurban Group | Industrials | $33.4B | Toll roads, infrastructure play |
| **MQG** | Macquarie Group | Financials | $43.8B | Investment bank, global exposure |
| **WDS** | Woodside Energy | Energy | $33.9B | LNG leader, energy transition |

**Total: 6/18 stocks (33%) - Provides growth and commodity exposure**

### **Tier 3: Mid-Large Cap Opportunities (4 stocks)**
*Higher growth potential, technology/healthcare exposure*

| **Symbol** | **Company** | **Sector** | **Market Cap** | **Rationale** |
|------------|-------------|-------------|----------------|---------------|
| **XRO** | Xero Limited | Technology | $6.7B | SaaS leader, global growth |
| **WTC** | WiseTech Global | Technology | $5.8B | Logistics software, AI integration |
| **REA** | REA Group | Communication | $10.7B | PropTech leader, digital real estate |
| **ALL** | Aristocrat Leisure | Consumer Disc. | $26.0B | Gaming technology, global expansion |

**Total: 4/18 stocks (22%) - Provides technology and growth exposure**

---

## 📈 Portfolio Characteristics

### **Sector Allocation**
- **Financials**: 27.8% (5 stocks) - CBA, WBC, ANZ, NAB, MQG
- **Materials**: 22.2% (3 stocks) - BHP, RIO, FMG  
- **Consumer Discretionary**: 16.7% (3 stocks) - WES, ALL, REA
- **Technology**: 11.1% (2 stocks) - XRO, WTC
- **Communication**: 11.1% (2 stocks) - TLS, REA
- **Healthcare**: 5.6% (1 stock) - CSL
- **Consumer Staples**: 5.6% (1 stock) - WOW
- **Industrials**: 5.6% (1 stock) - TCL
- **Energy**: 5.6% (1 stock) - WDS

### **Market Cap Distribution**
- **Mega Cap (>$50B)**: 9 stocks (50%)
- **Large Cap ($10-50B)**: 6 stocks (33%)
- **Mid-Large Cap ($5-10B)**: 3 stocks (17%)

### **Liquidity Profile**
- **Ultra High**: 8 stocks (ASX 20 constituents)
- **High**: 7 stocks (ASX 50 constituents) 
- **Medium-High**: 3 stocks (Active ASX 200)

---

## 🔄 Implementation Strategy

### **Phase 1: Core Deployment (Week 1)**
Deploy Tier 1 (8 stocks) first:
- Establish foundation with highest liquidity stocks
- Test data feeds and signal generation
- Validate risk management systems
- Build confidence with lowest-risk positions

### **Phase 2: Growth Addition (Week 2-3)**
Add Tier 2 (6 stocks):
- Introduce commodity and growth exposure
- Monitor correlation effects
- Adjust position sizing based on volatility
- Optimize rebalancing frequency

### **Phase 3: Opportunity Completion (Week 4)**
Add Tier 3 (4 stocks):
- Complete technology and growth allocation
- Fine-tune sector weightings
- Implement full portfolio optimization
- Monitor performance vs ASX 200 benchmark

### **Risk Management**
- **Single Stock Limit**: 8% maximum position size
- **Sector Limits**: 30% maximum sector exposure
- **Liquidity Buffer**: 5% cash allocation minimum
- **Correlation Monitoring**: Daily correlation analysis
- **Volatility Scaling**: Dynamic position sizing

---

## 📊 Expected Performance Characteristics

### **Target Metrics**
- **Sharpe Ratio**: 1.2-1.8 (vs ASX 200: ~0.8)
- **Maximum Drawdown**: <15% (vs ASX 200: ~20%)
- **Beta**: 0.9-1.1 (market neutral to slight growth bias)
- **Alpha Generation**: 3-8% annually vs ASX 200
- **Win Rate**: 55-65% (individual trades)

### **Risk Factors**
- **Banking Concentration**: 27.8% in financials
- **Commodity Exposure**: 22.2% materials sector
- **Interest Rate Sensitivity**: High via banking stocks
- **China Exposure**: Significant via mining stocks
- **Technology Risk**: Growth stock volatility

### **Correlation Benefits**
- **Low Correlation Pairs**: CSL/BHP, XRO/FMG, WTC/CBA
- **Defensive Balance**: Healthcare + Consumer Staples
- **Growth Balance**: Technology + Resources
- **Yield Balance**: Banks + Infrastructure

---

## 🔍 Alternative Considerations

### **Potential Substitutions**
If any primary stocks become unavailable or underperform:

**Banking Alternatives**:
- **BOQ** (Bank of Queensland) - Regional banking
- **BEN** (Bendigo Bank) - Community banking

**Technology Alternatives**:
- **NXT** (NextDC) - Data center REIT
- **TNE** (Technology One) - Enterprise software

**Healthcare Alternatives**:
- **COH** (Cochlear) - Medical devices
- **RHC** (Ramsay Health) - Healthcare services

**Materials Alternatives**:
- **S32** (South32) - Diversified mining
- **NCM** (Newcrest) - Gold mining

### **Scaling Considerations**
When graduating from free-tier to paid IBKR subscriptions:

**Add Sectors**:
- **REITs**: GMG, SCG, VCX (Real Estate)
- **Utilities**: AGL, ORG (Infrastructure)  
- **Small Caps**: High-growth opportunities

**Add Strategies**:
- **Pairs Trading**: CBA/ANZ, BHP/RIO
- **Sector Rotation**: Materials vs Financials
- **Options Overlay**: Income generation

---

## 🚀 Next Steps

### **Immediate Actions (This Week)**
1. **Validate IBKR Coverage**: Confirm all 18 stocks have reliable data feeds
2. **Test Data Quality**: Run 1-week paper trading simulation  
3. **Configure Risk Limits**: Set position and sector limits in system
4. **Backtest Portfolio**: Run 2-year historical simulation

### **Implementation Timeline**
- **Day 1-3**: Deploy Tier 1 (8 core stocks)
- **Day 4-7**: Monitor and optimize core positions
- **Week 2**: Add Tier 2 (6 growth/resources stocks)
- **Week 3**: Add Tier 3 (4 technology/opportunity stocks)
- **Week 4**: Full portfolio optimization and live deployment

### **Success Metrics**
- **Data Feed Reliability**: >99.5% uptime
- **Signal Generation**: 5-15 trades per day across portfolio
- **Risk Management**: Zero position limit breaches
- **Performance Tracking**: Daily vs ASX 200 comparison

---

## 📝 Notes & References

### **Research Sources**
- ASX 200 constituent data (Wikipedia, August 2025)
- ASX 20 liquidity analysis (Market Index)
- Market capitalization data (S&P Dow Jones Indices)
- Sector allocation methodology (GICS classification)

### **Strategy Integration**
- Implements `docs/ibkr_free_tier_strategy.md` stock selection guidelines
- Aligns with TODO.md Phase 3A.1 live market data requirements
- Supports 100 market data line limit optimization
- Enables future scaling path to paid IBKR tiers

### **Review Schedule**
- **Weekly**: Portfolio performance and correlation analysis
- **Monthly**: Sector allocation and rebalancing assessment  
- **Quarterly**: Stock selection review and potential substitutions
- **Semi-Annual**: Strategy effectiveness and scaling evaluation

---

*This selection represents the optimal balance of liquidity, diversification, and growth potential within IBKR free-tier constraints. The portfolio provides comprehensive ASX market exposure while maintaining the focus and risk management required for profitable algorithmic trading.*
