# q-signeringsportalen-api

Genbrugelig, synkron Python-klient til SG.DokSigner API.
https://signeringsportal.haderslev.dk/doksigner/swagger/index.html

## Ansvar

Biblioteket henter OAuth-token, kalder API'et, validerer svar og konverterer PDF-bytes til/fra Base64. Den kaldende proces ejer selv `item.data`, states, defer, lagring og den løbende polling.

## Credential i Automation Server

Navn: `API_SIGNERINGSPORTALEN`

- Password: OAuth `client_secret`, uden `Bearer`
- Data JSON:

```json
{
  "client_id": "DIN_CLIENT_ID"
}
```

## Installation

```bash
uv sync --extra dev
```

Kopiér `.env.example` til `.env` ved lokal kørsel. Indsæt aldrig secrets i repository'et.

## Kort eksempel

```python
from datetime import datetime, timedelta, timezone
from q_signeringsportalen_api import SigneringsportalClient

client = SigneringsportalClient.from_automation_server()
with open("dokument.pdf", "rb") as fil:
    pdf_bytes = fil.read()

resultat = client.opret_signeringsopgave(
    navn="Samtykkeerklæring",
    pdf_filer=[{"titel": "Samtykkeerklæring.pdf", "indhold": pdf_bytes}],
    underskrivere=[{
        "identifikator": "CPR_UDEN_BINDESTREG",
        "type": "DigitalPost",
        "besked": "Dokumentet skal underskrives.",
    }],
    udloeber=datetime.now(timezone.utc) + timedelta(days=14),
)
print(resultat.flow_id)
status = client.hent_signeringsstatus(resultat.flow_id)
print(status.status)
```

`hent_signeret_pdf()` returnerer PDF som `bytes`. Funktionen bruger som standard `SignaturgruppenBroker` og endpointet `GetPades`.
