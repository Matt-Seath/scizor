"""Add watchlist tables for user-defined market data collection

Revision ID: 20250826_085000
Revises: 89abcdef1234
Create Date: 2025-08-26 08:50:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250826_085000"
down_revision = "89abcdef1234"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add watchlist and watchlist_symbols tables"""
    
    # Create watchlists table
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_watchlists_id"), "watchlists", ["id"], unique=False)
    op.create_index("idx_watchlists_name", "watchlists", ["name"], unique=True)
    op.create_index("idx_watchlists_active", "watchlists", ["is_active"], unique=False)
    
    # Create watchlist_symbols table
    op.create_table(
        "watchlist_symbols",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watchlist_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=10), nullable=False),
        sa.Column("con_id", sa.BigInteger(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True, default=1),
        sa.Column("collect_intraday", sa.Boolean(), nullable=False, default=True),
        sa.Column("timeframes", sa.Text(), nullable=True, default='5min,15min,1hour'),
        sa.Column("added_at", sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(
            ["watchlist_id"], 
            ["watchlists.id"], 
            name="fk_watchlist_symbols_watchlist_id",
            ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["con_id"], 
            ["contract_details.con_id"], 
            name="fk_watchlist_symbols_con_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Create indexes for watchlist_symbols
    op.create_index(op.f("ix_watchlist_symbols_id"), "watchlist_symbols", ["id"], unique=False)
    op.create_index(
        "idx_watchlist_symbols_unique", 
        "watchlist_symbols", 
        ["watchlist_id", "symbol"], 
        unique=True
    )
    op.create_index(
        "idx_watchlist_symbols_active", 
        "watchlist_symbols", 
        ["watchlist_id", "collect_intraday"], 
        unique=False
    )
    op.create_index("idx_watchlist_symbols_symbol", "watchlist_symbols", ["symbol"], unique=False)
    op.create_index(
        "idx_watchlist_symbols_priority", 
        "watchlist_symbols", 
        ["watchlist_id", "priority"], 
        unique=False
    )


def downgrade() -> None:
    """Remove watchlist tables"""
    
    # Drop indexes first
    op.drop_index("idx_watchlist_symbols_priority", table_name="watchlist_symbols")
    op.drop_index("idx_watchlist_symbols_symbol", table_name="watchlist_symbols")
    op.drop_index("idx_watchlist_symbols_active", table_name="watchlist_symbols")
    op.drop_index("idx_watchlist_symbols_unique", table_name="watchlist_symbols")
    op.drop_index(op.f("ix_watchlist_symbols_id"), table_name="watchlist_symbols")
    
    # Drop watchlist_symbols table
    op.drop_table("watchlist_symbols")
    
    # Drop watchlist indexes and table
    op.drop_index("idx_watchlists_active", table_name="watchlists")
    op.drop_index("idx_watchlists_name", table_name="watchlists")
    op.drop_index(op.f("ix_watchlists_id"), table_name="watchlists")
    op.drop_table("watchlists")