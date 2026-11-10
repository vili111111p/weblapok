# E-mailek küldése

A leveleket a saját gépedről, a saját Gmail-fiókodból küldöd ki. Ehhez a `kuldo.py` program kell.

## Mi van itt

- **`demoval/`:** levelek csatolt demóval.
  - Airport Garázs, Gránit fogadó, Bell Állatorvos, Korona Szépségszalon, Julika Virág.
  - Az Öreg Harang levele is itt van, de neki nincs ismert e-mail címe.
  - A mellékletek a te `demok/` mappádból jönnek.
- **`demo_nelkul/`:** levelek demó nélkül, ingyenes demó ajánlásával (Venyige, Brasch).
- **`generalt/`:** a program ide írja a CSV-kből gyártott leveleket. Csak a te gépeden van, nem kerül fel a GitHubra.

Minden levélfájl így épül fel: fejléc (`CÍMZETT`, `TÁRGY`, `MELLÉKLET`), egy szaggatott vonal, a levél szövege, egy újabb vonal, és a végén a `JEGYZETEK`. A jegyzeteket a program nem küldi el.

## Lépések

1. **Másold be a fájlokat.** A `kuldes/` mappát tedd a weblapok mappádba, a CSV-k és a `demok/` mellé.
2. **Kapcsold be a kétlépcsős azonosítást a Google-fiókodban.** Ez kell ahhoz, hogy alkalmazásjelszót kérhess.
3. **Kérj alkalmazásjelszót.** A Google-fiókban: Biztonság → Alkalmazásjelszavak. Ez egy 16 betűs jelszó, a program küldéskor kéri be. Ne írd fájlba.
4. **Írd be az adataidat.** Első futtatáskor a program létrehozza a `kuldes/adataim.ini` fájlt. Ebbe írd a neved, a telefonszámod és az e-mail címed.
5. **Gyártsd le a többi cég levelét.** A CSV-kből a legjobb 30 cégnek, akinek van e-mail címe:
   ```bash
   python3 kuldes/kuldo.py general --darab 30
   ```
   Utána nézd át a `kuldes/generalt/` mappát, és töröld, ami nem odaillő.
6. **Nézd meg, mi menne ki.** Ez a lépés semmit nem küld:
   ```bash
   python3 kuldes/kuldo.py elonezet
   ```
7. **Próbaküldés.** Egyetlen levél megy ki, csak neked:
   ```bash
   python3 kuldes/kuldo.py kuld
   ```
8. **Éles küldés.** A program megkérdezi, biztos vagy-e. Egy futás legfeljebb 15 levelet küld, közöttük 1–2,5 perc szünettel:
   ```bash
   python3 kuldes/kuldo.py kuld --valoban
   ```

Az elküldött leveleket a program a `kuldve.csv` fájlba írja, így ugyanaz a cég nem kap kétszer levelet.

## Jó tudni

- **Ne küldj naponta 20–30 levélnél többet.** Különben a Gmail spamnek nézheti.
- **Ha valaki azt írja, hogy nem kér több levelet, többet ne írj neki.** Minden levél végén ott a mondat, hogy elég visszaírni. A magánszemélyek e-mail címeire (például vezetéknév.keresztnév@…) ez különösen igaz.
- **Ha valaki válaszol a demó nélküli levélre,** készíts neki demót (vagy kérj meg rá), és küldd el a `demoval/` formátumában.
