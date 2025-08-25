"""Recreate contract_details table with comprehensive IBKR fields

Revision ID: 89abcdef1234
Revises: 
Create Date: 2025-08-25 21:42:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "89abcdef1234"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Recreate contract_details table with comprehensive fields"""
    
    # Drop existing contract_details table (it's empty)
    op.drop_index(op.f("idx_contracts_symbol_exchange"), table_name="contract_details")
    op.drop_index(op.f("idx_contracts_updated_at"), table_name="contract_details")
    op.drop_table("contract_details")
    
    # Create comprehensive contract_details table
    op.create_table(
        "contract_details",
        # Core contract identification
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=10), nullable=False),
        sa.Column("con_id", sa.BigInteger(), nullable=False),
        sa.Column("sec_type", sa.String(length=10), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("exchange", sa.String(length=20), nullable=False),
        sa.Column("primary_exchange", sa.String(length=20), nullable=True),
        sa.Column("local_symbol", sa.String(length=20), nullable=True),
        sa.Column("trading_class", sa.String(length=20), nullable=True),
        
        # Company information
        sa.Column("long_name", sa.String(length=200), nullable=True),
        sa.Column("market_name", sa.String(length=50), nullable=True),
        
        # Industry classification
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("subcategory", sa.String(length=100), nullable=True),
        
        # Trading specifications
        sa.Column("min_tick", sa.DECIMAL(precision=10, scale=8), nullable=True),
        sa.Column("price_magnifier", sa.Integer(), nullable=True, default=sa.text("1")),
        sa.Column("md_size_multiplier", sa.Integer(), nullable=True, default=sa.text("1")),
        
        # Market rules and trading
        sa.Column("market_rule_ids", sa.Text(), nullable=True),
        sa.Column("order_types", sa.Text(), nullable=True),
        sa.Column("valid_exchanges", sa.Text(), nullable=True),
        
        # Trading hours
        sa.Column("trading_hours", sa.Text(), nullable=True),
        sa.Column("liquid_hours", sa.Text(), nullable=True),
        sa.Column("time_zone_id", sa.String(length=50), nullable=True),
        
        # Security identifiers
        sa.Column("sec_id_list", sa.Text(), nullable=True),
        sa.Column("stock_type", sa.String(length=20), nullable=True),
        sa.Column("cusip", sa.String(length=20), nullable=True),
        
        # Contract specifications (futures/options)
        sa.Column("contract_month", sa.String(length=10), nullable=True),
        sa.Column("last_trading_day", sa.Date(), nullable=True),
        sa.Column("real_expiration_date", sa.String(length=10), nullable=True),
        sa.Column("last_trade_time", sa.String(length=20), nullable=True),
        
        # Bond/Fixed Income fields
        sa.Column("bond_type", sa.String(length=50), nullable=True),
        sa.Column("coupon_type", sa.String(length=50), nullable=True),
        sa.Column("coupon", sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column("callable", sa.Boolean(), nullable=True, default=sa.text("false")),
        sa.Column("putable", sa.Boolean(), nullable=True, default=sa.text("false")),
        sa.Column("convertible", sa.Boolean(), nullable=True, default=sa.text("false")),
        sa.Column("maturity", sa.String(length=20), nullable=True),
        sa.Column("issue_date", sa.String(length=20), nullable=True),
        sa.Column("ratings", sa.String(length=100), nullable=True),
        
        # Options fields
        sa.Column("next_option_date", sa.String(length=20), nullable=True),
        sa.Column("next_option_type", sa.String(length=20), nullable=True),
        sa.Column("next_option_partial", sa.Boolean(), nullable=True, default=sa.text("false")),
        
        # Underlying contract (for derivatives)
        sa.Column("under_con_id", sa.BigInteger(), nullable=True),
        sa.Column("under_symbol", sa.String(length=20), nullable=True),
        sa.Column("under_sec_type", sa.String(length=10), nullable=True),
        
        # Additional metadata
        sa.Column("agg_group", sa.Integer(), nullable=True),
        sa.Column("ev_rule", sa.Text(), nullable=True),
        sa.Column("ev_multiplier", sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column("desc_append", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        
        # System fields
        sa.Column("created_at", sa.DateTime(), nullable=True, default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, default=sa.text("CURRENT_TIMESTAMP")),
        
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("con_id"),
    )
    
    # Create comprehensive indexes
    op.create_index("idx_contracts_symbol_exchange", "contract_details", ["symbol", "exchange"])
    op.create_index("idx_contracts_long_name", "contract_details", ["long_name"])
    op.create_index("idx_contracts_industry_category", "contract_details", ["industry", "category"])
    op.create_index("idx_contracts_stock_type", "contract_details", ["stock_type"])
    op.create_index("idx_contracts_trading_hours", "contract_details", ["time_zone_id"])
    op.create_index("idx_contracts_updated_at", "contract_details", ["updated_at"])
    op.create_index("idx_contracts_under_con_id", "contract_details", ["under_con_id"])
    op.create_index("idx_contracts_sec_type_currency", "contract_details", ["sec_type", "currency"])


def downgrade() -> None:
    """Revert to old limited contract_details schema"""
    
    # Drop comprehensive table
    op.drop_index("idx_contracts_sec_type_currency", table_name="contract_details")
    op.drop_index("idx_contracts_under_con_id", table_name="contract_details")
    op.drop_index("idx_contracts_updated_at", table_name="contract_details")
    op.drop_index("idx_contracts_trading_hours", table_name="contract_details")
    op.drop_index("idx_contracts_stock_type", table_name="contract_details")
    op.drop_index("idx_contracts_industry_category", table_name="contract_details")
    op.drop_index("idx_contracts_long_name", table_name="contract_details")
    op.drop_index("idx_contracts_symbol_exchange", table_name="contract_details")
    op.drop_table("contract_details")
    
    # Recreate old limited schema
    op.create_table(
        "contract_details",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.VARCHAR(length=10), autoincrement=False, nullable=False),
        sa.Column("con_id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("sec_type", sa.VARCHAR(length=10), autoincrement=False, nullable=False),
        sa.Column("currency", sa.VARCHAR(length=10), autoincrement=False, nullable=False),
        sa.Column("exchange", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("primary_exchange", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column("local_symbol", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column("trading_class", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column("min_tick", sa.NUMERIC(precision=10, scale=8), autoincrement=False, nullable=True),
        sa.Column("market_rule_ids", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("contract_month", sa.VARCHAR(length=10), autoincrement=False, nullable=True),
        sa.Column("last_trading_day", sa.DATE(), autoincrement=False, nullable=True),
        sa.Column("time_zone_id", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("con_id"),
    )
    op.create_index("idx_contracts_updated_at", "contract_details", ["updated_at"])
    op.create_index("idx_contracts_symbol_exchange", "contract_details", ["symbol", "exchange"])