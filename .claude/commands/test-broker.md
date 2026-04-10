# Test Broker Connection on Server

Test broker connections on the production server at `194.61.31.226`.

## Usage

- `/test-broker` — test all broker connections
- `/test-broker exchange1` — test only Exchange1
- `/test-broker binance` — test only Binance Testnet

## Test Script

Run this via SSH on the server:

```bash
ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@194.61.31.226 'cd /opt/algomatter/backend && .venv/bin/python3 -c "
import asyncio
from app.db.session import async_session_factory
from app.crypto.encryption import decrypt_credentials
from app.db.models import BrokerConnection
from app.brokers.factory import get_broker
from sqlalchemy import select

async def main():
    async with async_session_factory() as session:
        result = await session.execute(select(BrokerConnection))
        conns = result.scalars().all()
        for conn in conns:
            print(f\"=== {conn.broker_type} ===\")
            try:
                creds = decrypt_credentials(conn.tenant_id, conn.credentials)
                broker = await get_broker(conn.broker_type, creds)
                print(f\"  Auth: OK\")
                verified = await broker.verify_connection()
                print(f\"  Verified: {verified}\")
                balance = await broker.get_balance()
                print(f\"  Balance: available={balance.available}, total={balance.total}\")
                positions = await broker.get_positions()
                print(f\"  Positions: {len(positions)}\")
                await broker.close()
            except Exception as e:
                print(f\"  ERROR: {e}\")

asyncio.run(main())
"'
```

If a specific broker type is requested, filter by adding `.where(BrokerConnection.broker_type == \"<type>\")` to the query.

## Notes
- Exchange1 requires a browser User-Agent header to bypass WAF (already configured in adapter)
- Binance Testnet connects to `https://testnet.binance.vision`
