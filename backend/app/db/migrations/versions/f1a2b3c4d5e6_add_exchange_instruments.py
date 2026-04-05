"""add_exchange_instruments

Revision ID: f1a2b3c4d5e6
Revises: c3f1a2b4d5e6
Create Date: 2026-04-05 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'c3f1a2b4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Exchange1 supported instruments (spot + perpetual futures)
_E1_ASSETS = [
    ("BTC",   "BTCUSDT"),
    ("ETH",   "ETHUSDT"),
    ("BNB",   "BNBUSDT"),
    ("SOL",   "SOLUSDT"),
    ("XRP",   "XRPUSDT"),
    ("ADA",   "ADAUSDT"),
    ("DOGE",  "DOGEUSDT"),
    ("DOT",   "DOTUSDT"),
    ("LTC",   "LTCUSDT"),
    ("LINK",  "LINKUSDT"),
    ("AVAX",  "AVAXUSDT"),
    ("MATIC", "MATICUSDT"),
    ("UNI",   "UNIUSDT"),
    ("ATOM",  "ATOMUSDT"),
    ("TRX",   "TRXUSDT"),
    ("SHIB",  "SHIBUSDT"),
    ("TON",   "TONUSDT"),
    ("NEAR",  "NEARUSDT"),
    ("FIL",   "FILUSDT"),
    ("ARB",   "ARBUSDT"),
    ("OP",    "OPUSDT"),
    ("SUI",   "SUIUSDT"),
    ("APT",   "APTUSDT"),
    ("BCH",   "BCHUSDT"),
    ("ETC",   "ETCUSDT"),
    ("INJ",   "INJUSDT"),
    ("SAND",  "SANDUSDT"),
    ("MANA",  "MANAUSDT"),
    ("CRV",   "CRVUSDT"),
    ("AAVE",  "AAVEUSDT"),
    ("MKR",   "MKRUSDT"),
    ("COMP",  "COMPUSDT"),
    ("1INCH", "1INCHUSDT"),
    ("IMX",   "IMXUSDT"),
    ("RUNE",  "RUNEUSDT"),
    ("FTM",   "FTMUSDT"),
    ("ALGO",  "ALGOUSDT"),
    ("VET",   "VETUSDT"),
    ("ICP",   "ICPUSDT"),
    ("HBAR",  "HBARUSDT"),
]


def upgrade() -> None:
    op.create_table(
        "exchange_instruments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("exchange", sa.String(50), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("base_asset", sa.String(20), nullable=False),
        sa.Column("quote_asset", sa.String(20), nullable=False),
        sa.Column("product_type", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange", "symbol", "product_type",
                            name="uq_exchange_instruments"),
    )
    op.create_index(
        "ix_exchange_instruments_exchange",
        "exchange_instruments",
        ["exchange"],
    )

    rows = []
    for base, symbol in _E1_ASSETS:
        for product_type in ("SPOT", "FUTURES"):
            rows.append(
                f"('EXCHANGE1', '{symbol}', '{base}', 'USDT', '{product_type}', true)"
            )

    op.execute(
        "INSERT INTO exchange_instruments "
        "(exchange, symbol, base_asset, quote_asset, product_type, is_active) VALUES "
        + ", ".join(rows)
    )


def downgrade() -> None:
    op.drop_index("ix_exchange_instruments_exchange", table_name="exchange_instruments")
    op.drop_table("exchange_instruments")
