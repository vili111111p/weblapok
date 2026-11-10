#!/usr/bin/env python3
"""
Megkereső e-mailek előnézete, legyártása és küldése.

Használat (a weblapok mappából):
    python3 kuldes/kuldo.py general     # a CSV-kből levelet ír a többi cégnek (kuldes/generalt/)
    python3 kuldes/kuldo.py elonezet    # megmutatja, mi menne ki és kinek; semmit nem küld
    python3 kuldes/kuldo.py kuld        # PRÓBA: csak magadnak küld egy példányt
    python3 kuldes/kuldo.py kuld --valoban   # tényleges küldés a cégeknek

A saját adataidat a kuldes/adataim.ini fájlba írd (először a program létrehozza).
A Gmail alkalmazásjelszót NE írd fájlba: a program a küldéskor bekéri.
"""
import configparser, csv, getpass, glob, html, mimetypes, os, random, re, smtplib, ssl, sys, time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

GYOKER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # weblapok/
KULDES = os.path.join(GYOKER, "kuldes")
MAPPAK = ["demoval", "demo_nelkul", "generalt"]
NAPLO = os.path.join(KULDES, "kuldve.csv")
ADATOK = os.path.join(KULDES, "adataim.ini")
CSV_FORRASOK = ["weboldal_nelkuli_cegek.csv", "cegek_meglevo_arculattal.csv"]
ELVALASZTO = re.compile(r"^-{10,}\s*$", re.M)

# ------------------------------------------------------------------ beállítások
def adatok():
    if not os.path.exists(ADATOK):
        with open(ADATOK, "w", encoding="utf-8") as f:
            f.write("[en]\nnev = \ntelefon = \nemail = \n\n"
                    "[kuldes]\n# Gmail esetén ezt hagyd így\nsmtp = smtp.gmail.com\nport = 465\n"
                    "# egy futásban legfeljebb ennyi levél (a spamszűrők miatt maradj 20 alatt)\nmax_level = 15\n"
                    "# ennyi másodpercet vár két levél között (min-max)\nszunet = 60-150\n")
        sys.exit(f"Létrehoztam: {ADATOK}\nÍrd bele a neved, telefonszámod és e-mail címed, aztán futtasd újra.")
    c = configparser.ConfigParser(); c.read(ADATOK, encoding="utf-8")
    en = {k: c.get("en", k, fallback="").strip() for k in ("nev", "telefon", "email")}
    hiany = [k for k, v in en.items() if not v]
    if hiany:
        sys.exit(f"Hiányzik az adataim.ini-ből: {', '.join(hiany)}")
    k = c["kuldes"] if c.has_section("kuldes") else {}
    a, b = (k.get("szunet", "60-150").split("-") + ["150"])[:2]
    return en, {"smtp": k.get("smtp", "smtp.gmail.com"), "port": int(k.get("port", 465)),
                "max": int(k.get("max_level", 15)), "szunet": (int(a), int(b))}

# ------------------------------------------------------------------ levélfájlok
def beolvas(ut):
    s = open(ut, encoding="utf-8").read()
    reszek = ELVALASZTO.split(s)
    if len(reszek) < 2:
        return None
    fej, torzs = reszek[0], reszek[1].strip("\n")
    mezok = {}
    for sor in fej.splitlines():
        if ":" in sor and not sor.startswith("#"):
            k, v = sor.split(":", 1); mezok[k.strip().upper()] = v.strip()
    return {"fajl": os.path.relpath(ut, GYOKER), "cimzett": mezok.get("CÍMZETT", ""),
            "targy": mezok.get("TÁRGY", ""), "melleklet": mezok.get("MELLÉKLET", ""), "torzs": torzs}

def kitolt(szoveg, en):
    return (szoveg.replace("[Neved]", en["nev"]).replace("[telefonszámod]", en["telefon"])
                  .replace("[e-mail címed]", en["email"]))

def levelek(en):
    out = []
    for m in MAPPAK:
        for ut in sorted(glob.glob(os.path.join(KULDES, m, "*.txt"))):
            l = beolvas(ut)
            if not l:
                continue
            l["torzs"] = kitolt(l["torzs"], en); l["targy"] = kitolt(l["targy"], en)
            l["hiba"] = ellenoriz(l)
            out.append(l)
    return out

EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[a-z]{2,}$", re.I)
def ellenoriz(l):
    if not l["cimzett"]:
        return "nincs címzett"
    if not EMAIL_RE.match(l["cimzett"]):
        return f"hibás cím: {l['cimzett']}"
    if re.search(r"\[(Neved|telefonszámod|e-mail címed)\]", l["torzs"]):
        return "kitöltetlen saját adat"
    if l["melleklet"] and not os.path.exists(os.path.join(GYOKER, l["melleklet"])):
        return f"hiányzó melléklet: {l['melleklet']}"
    return ""

def naplo_cimek():
    if not os.path.exists(NAPLO):
        return set()
    with open(NAPLO, encoding="utf-8") as f:
        return {r["cimzett"].lower() for r in csv.DictReader(f) if r.get("allapot") == "elkuldve"}

def naploz(l, allapot):
    uj = not os.path.exists(NAPLO)
    with open(NAPLO, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if uj:
            w.writerow(["ido", "cimzett", "fajl", "targy", "allapot"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M"), l["cimzett"], l["fajl"], l["targy"], allapot])

# ------------------------------------------------------------------ üzenet
def html_torzs(t):
    e = html.escape(t)
    e = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", e)
    bek = []
    for b in re.split(r"\n\s*\n", e):
        sorok = b.split("\n")
        if all(s.startswith("- ") for s in sorok):
            bek.append("<ul>" + "".join(f"<li>{s[2:]}</li>" for s in sorok) + "</ul>")
        else:
            bek.append("<p>" + "<br>".join(sorok) + "</p>")
    return ('<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.5;color:#222">'
            + "".join(bek) + "</div>")

def uzenet(l, en, cimzett=None):
    m = EmailMessage()
    m["From"] = f"{en['nev']} <{en['email']}>"
    m["To"] = cimzett or l["cimzett"]
    m["Subject"] = l["targy"]
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain=en["email"].split("@")[-1])
    sima = l["torzs"].replace("**", "")
    m.set_content(sima)
    m.add_alternative(html_torzs(l["torzs"]), subtype="html")
    if l["melleklet"]:
        ut = os.path.join(GYOKER, l["melleklet"])
        tip = (mimetypes.guess_type(ut)[0] or "application/octet-stream").split("/")
        nev = os.path.basename(ut)
        if nev == "index.html":
            nev = os.path.basename(os.path.dirname(ut)) + "_demo.html"
        with open(ut, "rb") as f:
            m.add_attachment(f.read(), maintype=tip[0], subtype=tip[1], filename=nev)
    return m

# ------------------------------------------------------------------ parancsok
def elonezet(en):
    kuldott = naplo_cimek()
    jo = 0
    print(f"{'ÁLLAPOT':<28} {'CÍMZETT':<34} FÁJL")
    for l in levelek(en):
        if l["cimzett"].lower() in kuldott:
            all_ = "már elküldve"
        elif l["hiba"]:
            all_ = "KIHAGYVA: " + l["hiba"]
        else:
            all_ = "mehet"; jo += 1
        print(f"{all_[:28]:<28} {l['cimzett'][:34]:<34} {l['fajl']}")
        if len(all_) > 28:
            print(f"{'':<28} -> {all_}")
    print(f"\n{jo} levél küldhető.")

def kuld(en, beall, valoban):
    kuldott = naplo_cimek()
    sor = [l for l in levelek(en) if not l["hiba"] and l["cimzett"].lower() not in kuldott]
    if not sor:
        sys.exit("Nincs küldhető levél (lásd: elonezet).")
    if not valoban:
        sor = sor[:1]
        print(f"PRÓBA: egy példány ({sor[0]['fajl']}) megy CSAK NEKED: {en['email']}")
    else:
        sor = sor[:beall["max"]]
        print(f"{len(sor)} levél megy ki a cégeknek:")
        for l in sor:
            print("  -", l["cimzett"], "|", l["targy"])
        if input("Biztosan elküldöd? Írd be: igen  > ").strip().lower() != "igen":
            sys.exit("Megszakítva, semmi nem ment ki.")
    jelszo = os.environ.get("GMAIL_APP_JELSZO") or getpass.getpass(
        f"Alkalmazásjelszó ehhez: {en['email']} (nem jelenik meg gépelés közben): ")
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(beall["smtp"], beall["port"], context=ctx) as s:
        s.login(en["email"], jelszo)
        for i, l in enumerate(sor):
            try:
                s.send_message(uzenet(l, en, None if valoban else en["email"]))
                print("✓", l["cimzett"] if valoban else en["email"], "–", l["fajl"])
                if valoban:
                    naploz(l, "elkuldve")
            except Exception as e:
                print("✗", l["cimzett"], e)
                if valoban:
                    naploz(l, f"hiba: {e}")
            if valoban and i < len(sor) - 1:
                v = random.randint(*beall["szunet"]); print(f"  várok {v} mp…"); time.sleep(v)
    if not valoban:
        print("Nézd meg a postafiókodban, jól jelenik-e meg. Ha igen: python3 kuldes/kuldo.py kuld --valoban")

# ------------------------------------------------------------------ generálás a CSV-kből
def oszlop(fej, *kulcsok):
    kis = {h: h.lower().replace("é", "e").replace("á", "a").replace("ő", "o").replace("ó", "o")
           .replace("ű", "u").replace("ú", "u").replace("í", "i").replace("ü", "u").replace("ö", "o") for h in fej}
    for k in kulcsok:
        for h, n in kis.items():
            if n == k:
                return h
    for k in kulcsok:
        for h, n in kis.items():
            if k in n:
                return h
    return None

AGAK = [
    ("vendeglatas", r"restaurant|etterem|vendeglo|cafe|kavez|pizz|bar\b|pub|fast_food|cukrasz|confectionery|bistro|csarda|borozo",
     ["a pontos nyitvatartás és az étlap vagy napi menü egy helyen, telefonról is jól olvashatóan",
      "asztalfoglalás vagy rendezvénykérés egy gombbal"]),
    ("auto", r"car_repair|car|auto|szerviz|gumi|tyres|karosszeria|kipufogo",
     ["a szolgáltatások listája és egy gombbal hívható telefonszám",
      "időpontkérés űrlapon, amin az ügyfél előre leírja a hibát"]),
    ("szallas", r"hotel|guest_house|apartment|szallas|panzio|vendeghaz|fogado|motel|camping",
     ["szobák, árak és képek egy helyen",
      "közvetlen foglalási kérés, foglalási portálok jutaléka nélkül"]),
    ("szepseg", r"hairdresser|beauty|fodrasz|kozmetik|szepseg|nail|massage|masszaz",
     ["a szolgáltatások és árak áttekinthető listája",
      "időpontfoglalás néhány kattintással"]),
    ("egeszseg", r"dentist|doctor|veterinar|allatorv|orvos|fogorv|clinic|pharmacy|gyogyszert",
     ["a rendelési idők jól olvashatóan",
      "időpontkérés űrlapon, telefonálás nélkül"]),
]
ALT = ["a nyitvatartás, a cím és a szolgáltatások egy helyen, telefonról is jól olvashatóan",
       "egy gombbal hívható telefonszám és útvonaltervezés"]

GEN_SABLON = """CÍMZETT: {email}
TÁRGY: Ingyenes weboldal-terv – {nev}
-----------------------------------------------------------------
Tisztelt {nev}!

[Neved] vagyok, weboldalakat készítek kisvállalkozásoknak. Azért írok, mert {helyzet} Aki {hol}önöket keresi a telefonján, nem talál egy helyen pontos információt.

Egy egyszerű, telefonon jól használható oldal ezen segítene:

- {p1}
- {p2}

**Ha érdekli, ingyen elkészítek egy demót, amin megnézheti, hogyan nézne ki az önök oldala.** Ez semmire nem kötelez, és ez csak egy elképzelés lenne, bármit lehet rajta változtatni.

Magamról: 17 éves vagyok, és megbízási szerződéssel dolgozom, amit a szüleim is aláírnak, így minden hivatalos, és a díjról rendes papír készül.

Elég, ha visszaír egy „érdekel”-t, és pár napon belül küldöm a demót.

Üdvözlettel:
[Neved]
[telefonszámod]
[e-mail címed]

Ha nem szeretne több levelet kapni tőlem, elég egy rövid válasz, és többet nem keresem.
-----------------------------------------------------------------
JEGYZETEK (ezt nem küldi el a program)
- Forrás: {forras}, pontszám: {pont}, típus: {tipus}
- Küldés előtt nézd át: jó-e a megszólítás, működik-e még a cég.
"""

def fajlnev(s):
    s = s.lower()
    for a, b in zip("áéíóöőúüű", "aeiooouuu"):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:40] or "ceg"

def general(darab):
    meglevo = {l["cimzett"].lower() for m in MAPPAK[:2] for l in
               filter(None, (beolvas(p) for p in glob.glob(os.path.join(KULDES, m, "*.txt"))))}
    meglevo |= naplo_cimek()
    jelolt = []
    for forras in CSV_FORRASOK:
        ut = os.path.join(GYOKER, forras)
        if not os.path.exists(ut):
            print("Nem találom:", forras); continue
        with open(ut, encoding="utf-8-sig", newline="") as f:
            minta = f.read(4096); f.seek(0)
            try:
                dial = csv.Sniffer().sniff(minta, delimiters=",;\t")
            except csv.Error:
                dial = csv.excel
            r = csv.DictReader(f, dialect=dial)
            fej = r.fieldnames or []
            o = {"nev": oszlop(fej, "nev", "name", "cegnev"),
                 "email": oszlop(fej, "email", "e-mail", "contact:email", "mail"),
                 "varos": oszlop(fej, "varos", "telepules", "addr:city", "city"),
                 "tipus": oszlop(fej, "tipus", "kategoria", "category", "type"),
                 "allapot": oszlop(fej, "allapot", "status", "csoport"),
                 "web": oszlop(fej, "website", "weboldal", "regi_oldal", "url"),
                 "pont": oszlop(fej, "pontszam", "pont", "score")}
            print(f"{forras}: oszlopok -> " + ", ".join(f"{k}={v}" for k, v in o.items()))
            if not o["email"] or not o["nev"]:
                print("  ! Nincs e-mail vagy név oszlop, kihagyom."); continue
            for sor in r:
                em = (sor.get(o["email"]) or "").strip().split(";")[0].strip()
                if not EMAIL_RE.match(em) or em.lower() in meglevo:
                    continue
                meglevo.add(em.lower())
                try:
                    pont = float((sor.get(o["pont"]) or "0").replace(",", ".")) if o["pont"] else 0
                except ValueError:
                    pont = 0
                jelolt.append({"forras": forras, "pont": pont, "email": em,
                               **{k: (sor.get(v) or "").strip() if v else "" for k, v in o.items()
                                  if k not in ("email", "pont")}})
    jelolt.sort(key=lambda x: -x["pont"])
    cel = os.path.join(KULDES, "generalt"); os.makedirs(cel, exist_ok=True)
    for i, j in enumerate(jelolt[:darab], 1):
        tip = (j["tipus"] + " " + j["nev"]).lower()
        p1, p2 = next((p for _, rx, p in AGAK if re.search(rx, tip)), ALT)
        all_ = j["allapot"].lower()
        if "megsz" in all_ or "dead" in all_ or "halott" in all_:
            helyzet = (f"a korábbi weboldaluk ({j['web']}) már nem érhető el." if j["web"]
                       else "a korábbi weboldaluk már nem érhető el.")
        elif "elav" in all_ or "old" in all_:
            helyzet = (f"a jelenlegi weboldaluk ({j['web']}) telefonon nehezen használható." if j["web"]
                       else "a jelenlegi weboldaluk telefonon nehezen használható.")
        else:
            helyzet = "jelenleg nincs saját weboldaluk."
        hol = f"{j['varos']} környékén " if j["varos"] else ""
        szoveg = GEN_SABLON.format(email=j["email"], nev=j["nev"], helyzet=helyzet, hol=hol, p1=p1, p2=p2,
                                   forras=j["forras"], pont=j["pont"], tipus=j["tipus"] or "?")
        with open(os.path.join(cel, f"{i:03d}_{fajlnev(j['nev'])}.txt"), "w", encoding="utf-8") as f:
            f.write(szoveg)
    print(f"\n{min(darab, len(jelolt))} levél kész itt: kuldes/generalt/  (összesen {len(jelolt)} jelölt e-mail címmel)")
    print("Nézd át őket, a nem odaillőket töröld, aztán: python3 kuldes/kuldo.py elonezet")

if __name__ == "__main__":
    arg = sys.argv[1:]
    if not arg or arg[0] not in ("general", "elonezet", "kuld"):
        sys.exit(__doc__)
    if arg[0] == "general":
        n = int(arg[arg.index("--darab") + 1]) if "--darab" in arg else 30
        general(n)
    else:
        en, beall = adatok()
        elonezet(en) if arg[0] == "elonezet" else kuld(en, beall, "--valoban" in arg)
