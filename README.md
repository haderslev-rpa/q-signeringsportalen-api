# q-signeringsportalen-api

Genbrugelig, synkron Python-klient til SG.DokSigner API.

Swagger:
https://signeringsportal.haderslev.dk/doksigner/swagger/index.html

## Formål

Biblioteket skjuler tekniske detaljer om Signeringsportalen for den kaldende proces:

- henter OAuth-token med client credentials
- genbruger tokenet, indtil det nærmer sig udløb
- sender bearer-token til Signeringsportalen
- validerer UUID'er, tekst, datoer og PDF-bytes
- konverterer PDF-bytes til Base64 ved oprettelse
- konverterer den signerede PAdES-PDF fra Base64 til bytes ved hentning
- oversætter HTTP- og svarfejl til tydelige Python-fejltyper

Den kaldende proces ejer selv:

- `item.data["box"]`
- Automation Server-states og work-item-status
- `defer` og tidspunktet for næste statuskontrol
- lagring af `flow_id`, status og signer-id'er
- lagring eller videre behandling af den signerede PDF

Biblioteket ændrer ikke et Automation Server-work item.



## Automation Server-credential

Credential-navn:

```text
API_SIGNERINGSPORTALEN
```

Felter:

- Password: OAuth `client_secret`, uden teksten `Bearer`
- Data JSON: OAuth `client_id`

```json
{
  "client_id": "DIN_CLIENT_ID"
}
```

Secrets må ikke hardkodes i Python-kode, README eller tests.

## Opret klienten

Brug normalt klienten som context manager. Så lukkes den underliggende HTTP-klient automatisk:

```python
from q_signeringsportalen_api import SigneringsportalClient

with SigneringsportalClient.from_automation_server() as client:
    resultat = client.test_forbindelse()
```

`test_forbindelse()` returnerer:

```python
{
    "api_user_id": "UUID",
    "pending": [],
}
```

`api_user_id` er Signeringsportalens bruger-id. Det er ikke nødvendigvis det samme som OAuth `client_id`.

## Ansvarsfordeling i en proces

Et typisk procesflow er:

1. Processen læser eller genererer PDF som `bytes`.
2. Processen kalder `opret_signeringsopgave()`.
3. Processen gemmer det returnerede `flow_id` i `item.data["box"]`.
4. Processen sætter work item til venteposition efter eget procesmønster.
5. Processen kalder senere `hent_signeringsstatus(flow_id)`.
6. Ved status `Signed` kalder processen `hent_signeret_pdf(flow_id)`.
7. Processen gemmer eller videresender selv de returnerede PDF-bytes.

## Modtagertyper

Følgende værdier understøttes:

```text
Mail
DigitalPost
DigitalPostCvr
```

Identifikatoren afhænger af typen:

- `Mail`: mailadresse
- `DigitalPost`: CPR-nummer
- `DigitalPostCvr`: CVR-nummer

## Kontrollér Digital Post før oprettelse

CPR:

```python
with SigneringsportalClient.from_automation_server() as client:
    kan_modtage = client.kan_modtage_digital_post_cpr("0101011234")

if not kan_modtage:
    raise RuntimeError("Borgeren kan ikke modtage Digital Post.")
```

CVR:

```python
with SigneringsportalClient.from_automation_server() as client:
    kan_modtage = client.kan_modtage_digital_post_cvr("12345678")
```

Funktionerne returnerer `True` eller `False`.

## Opret signeringsopgave med mail

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

from q_signeringsportalen_api import SigneringsportalClient

pdf_bytes = Path("dokument.pdf").read_bytes()

with SigneringsportalClient.from_automation_server() as client:
    resultat = client.opret_signeringsopgave(
        navn="Samtykkeerklæring",
        pdf_filer=[
            {
                "titel": "Samtykkeerklæring.pdf",
                "indhold": pdf_bytes,
            }
        ],
        underskrivere=[
            {
                "identifikator": "modtager@eksempel.dk",
                "type": "Mail",
                "besked": "Dokumentet skal underskrives.",
            }
        ],
        udloeber=datetime.now(timezone.utc) + timedelta(days=14),
        should_creator_sign=False,
        is_structured=False,
    )

flow_id = resultat.flow_id
```

`pdf_filer[].indhold` skal være `bytes`, og indholdet skal begynde med `%PDF-`.

## Opret signeringsopgave med CPR og Digital Post

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

from q_signeringsportalen_api import SigneringsportalClient

cpr = "0101011234"
pdf_bytes = Path("dokument.pdf").read_bytes()

with SigneringsportalClient.from_automation_server() as client:
    if not client.kan_modtage_digital_post_cpr(cpr):
        raise RuntimeError("Borgeren kan ikke modtage Digital Post.")

    resultat = client.opret_signeringsopgave(
        navn="Samtykkeerklæring",
        pdf_filer=[
            {
                "titel": "Samtykkeerklæring.pdf",
                "indhold": pdf_bytes,
            }
        ],
        underskrivere=[
            {
                "identifikator": cpr,
                "type": "DigitalPost",
                "besked": "Dokumentet skal underskrives.",
            }
        ],
        udloeber=datetime.now(timezone.utc) + timedelta(days=14),
    )
```

Biblioteket logger ikke CPR, CVR, PDF-indhold, client secret eller bearer-token.

## Flere PDF-filer i samme workflow

Flere PDF-filer sendes i samme liste:

```python
resultat = client.opret_signeringsopgave(
    navn="Aftale med bilag",
    pdf_filer=[
        {
            "titel": "aftale.pdf",
            "indhold": aftale_bytes,
        },
        {
            "titel": "bilag.pdf",
            "indhold": bilag_bytes,
        },
    ],
    underskrivere=[
        {
            "identifikator": "modtager@eksempel.dk",
            "type": "Mail",
            "besked": "Aftalen og bilaget skal underskrives.",
        }
    ],
)
```

Ved hentning returnerer Signeringsportalen én samlet underskrevet PAdES-PDF. `hent_signeret_pdf()` returnerer derfor ét `bytes`-objekt, også når workflowet blev oprettet med flere PDF-filer.

## Hent status

```python
with SigneringsportalClient.from_automation_server() as client:
    status = client.hent_signeringsstatus(flow_id)

print(status.flow_id)
print(status.navn)
print(status.status)
print(status.udloeber)
print(status.er_signeret)
print(status.afventer)
print(status.er_afsluttet_uden_signatur)
```

Mulige statusværdier:

```text
Pending
Signed
Inactive
Expired
Deleted
```

Praktiske properties:

- `status.afventer` er `True` ved `Pending`
- `status.er_signeret` er `True` ved `Signed`
- `status.er_afsluttet_uden_signatur` er `True` ved `Inactive`, `Expired` eller `Deleted`

## Underskrivere og id'er

```python
for underskriver in status.underskrivere:
    print(underskriver.sign_flow_id)
    print(underskriver.signer_id)
    print(underskriver.modtagertype)
    print(underskriver.status)
```

De to id'er må ikke forveksles:

- `sign_flow_id` identificerer underskriverens signeringsforløb
- `signer_id` identificerer modtageren og skal bruges ved `send_paamindelse()`

Brug aldrig `sign_flow_id` som `signer_id` i påmindelseskaldet.

## Send påmindelse

Påmindelser bør kun sendes til en underskriver med status `Pending`.

```python
with SigneringsportalClient.from_automation_server() as client:
    status = client.hent_signeringsstatus(flow_id)

    underskriver = status.underskrivere[0]

    if status.afventer and underskriver.status == "Pending":
        if not underskriver.signer_id:
            raise RuntimeError("Signeringsportalen returnerede ikke signer_id.")

        client.send_paamindelse(
            flow_id=flow_id,
            signer_id=underskriver.signer_id,
        )
```

Funktionen returnerer `None`, når API'et har accepteret påmindelseskaldet.

## Hent den signerede PDF

```python
with SigneringsportalClient.from_automation_server() as client:
    status = client.hent_signeringsstatus(flow_id)

    if not status.er_signeret:
        raise RuntimeError(
            f"Workflowet er ikke signeret. Aktuel status: {status.status}"
        )

    signed_pdf_bytes = client.hent_signeret_pdf(flow_id)
```

`signed_pdf_bytes` er et `bytes`-objekt i memory. Funktionen gemmer ikke noget på disk.

Den kaldende proces kan eksempelvis sende bytes videre til et andet API eller gemme dem:

```python
from pathlib import Path

Path("underskrevet.pdf").write_bytes(signed_pdf_bytes)
```

## Slet signeringsopgave

```python
with SigneringsportalClient.from_automation_server() as client:
    client.slet_signeringsopgave(flow_id)
```

Funktionen returnerer `None`, når API'et har accepteret sletningen. Processen bør kun kalde funktionen, når dens egen forretningslogik har besluttet, at workflowet må slettes.

## Hent alle afventende workflows

```python
with SigneringsportalClient.from_automation_server() as client:
    resultat = client.hent_afventende_signeringsopgaver()

api_user_id = resultat["currentUserId"]
pending = resultat.get("pending") or []
```

Funktionen returnerer API'ets dictionary med:

- `currentUserId`
- `pending`

Da funktionen returnerer rå API-data, skal den kaldende kode selv håndtere felter og eventuelle `null`-værdier.

## Hent alle underskrevne workflows

```python
with SigneringsportalClient.from_automation_server() as client:
    resultat = client.hent_underskrevne_signeringsopgaver()

api_user_id = resultat["currentUserId"]
signed = resultat.get("signed") or []
```

Funktionen returnerer API'ets dictionary med:

- `currentUserId`
- `signed`

Brug normalt `hent_signeringsstatus(flow_id)`, når en proces allerede kender sit eget `flow_id`. Listefunktionerne er bedst til oversigter, fejlsøgning eller administrative jobs.

## API-bruger

OAuth `client_id` og Signeringsportalens `api_user_id` er forskellige begreber.

Hent én API-bruger:

```python
api_klient = client.hent_api_klient(api_user_id)
```

Opdatér navn og mailadresse:

```python
api_klient = client.opdater_api_klient(
    api_user_id,
    navn="Haderslev Automatisering",
    mail="automatisering@eksempel.dk",
)
```

Mailadressen bruges af Signeringsportalen til kvitteringer for fuldførte workflows.

## Gem relevante oplysninger i processens box

Eksempel på enkel datastruktur:

```python
box["signeringsportal"] = {
    "flow_id": resultat.flow_id,
    "status": "Pending",
    "created_at": datetime.now(timezone.utc).isoformat(),
}
```

Efter statuskontrol:

```python
status = client.hent_signeringsstatus(
    box["signeringsportal"]["flow_id"]
)

box["signeringsportal"]["status"] = status.status
box["signeringsportal"]["updated_at"] = (
    datetime.now(timezone.utc).isoformat()
)
```

Processen skal selv gemme `box` på work itemet efter det normale procesmønster.

## Fejltyper

Alle integrationsfejl arver fra:

```python
SigneringsportalError
```

Offentlige fejltyper:

- `SigneringsportalConfigurationError`: credential eller konfiguration mangler
- `SigneringsportalValidationError`: input er ugyldigt
- `SigneringsportalAuthenticationError`: token eller API-adgang afvises
- `SigneringsportalConnectionError`: forbindelsesfejl eller timeout
- `SigneringsportalApiError`: API'et returnerer en fejlstatus
- `SigneringsportalResponseError`: API-svaret har et uventet format

Eksempel:

```python
from q_signeringsportalen_api import (
    SigneringsportalClient,
    SigneringsportalConnectionError,
    SigneringsportalError,
    SigneringsportalValidationError,
)

try:
    with SigneringsportalClient.from_automation_server() as client:
        status = client.hent_signeringsstatus(flow_id)
except SigneringsportalValidationError:
    raise
except SigneringsportalConnectionError:
    raise
except SigneringsportalError:
    raise
```

Processen bestemmer selv, hvilke fejl der er midlertidige, og hvilke der skal stoppe et work item permanent.

## Sikkerhed og logging

- Log aldrig bearer-token eller client secret.
- Log ikke PDF-bytes eller Base64-indhold.
- Undgå CPR og CVR i almindelige logs.
- Gem ikke secrets i repositoryet.
- Brug `flow_id` til teknisk sporing.
- Brug `with SigneringsportalClient.from_automation_server()` for sikker lukning af HTTP-klienten.

## Tests

Testfiler ligger i:

```text
tests/
```

Genererede lokale testresultater ligger i:

```text
tests_local/
```

`tests_local/` er ignoreret af Git.

Flere tests er manuelle integrationstests og kan oprette, sende, påminde eller slette rigtige workflows. Læs testens docstring og kontrollér testinput før kørsel.
