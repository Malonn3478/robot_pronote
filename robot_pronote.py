from playwright.sync_api import sync_playwright
import requests
from datetime import datetime
import os
import time
from dotenv import load_dotenv
load_dotenv()

USERNAME = os.getenv("ENT_USERNAME")
PASSWORD = os.getenv("ENT_PASSWORD")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

absences_envoyees = set()
presence_envoyee = False

def envoyer_notification(message):
    payload = {"content": message}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

def lancer_robot():
    global presence_envoyee
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--start-maximized"])
        context = browser.new_context(no_viewport=True)
        page = context.new_page()

        try:
            # Connexion ENT
            page.goto("https://cas.mon-ent-occitanie.fr/login?service=https%3A%2F%2Fwww.mon-ent-occitanie.fr%2Fsg.do%3FPROC%3DIDENTIFICATION_FRONT")
            page.locator("//button[text()[contains(.,'ou parent')]]").click()
            page.locator('//label[@for="idp-MONT-EDU_parent_eleve"]').click()
            page.locator('//input[@id="button-submit"]').click()
            page.wait_for_selector('//button[@id="bouton_eleve"]', state="visible")
            page.locator('//button[@id="bouton_eleve"]').click()
            page.fill('//input[@id="username"]', USERNAME)
            page.fill('//input[@id="password"]', PASSWORD)
            page.click('//button[@id="bouton_valider"]')
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)

            # Aller sur Pronote
            page.evaluate("""
                const span = Array.from(document.querySelectorAll('span')).find(
                    e => e.textContent.includes('Site inter-établissements')
                );
                if (span) {
                    const event = new MouseEvent('click', { bubbles: true });
                    span.dispatchEvent(event);
                }
            """)
            page.click("//a[text()='LYCEE JEAN MOULIN']")
            page.goto("https://jean-moulin-beziers.mon-ent-occitanie.fr/sg.do?PROC=PAGE_ACCUEIL&ACTION=VALIDER")

            with context.expect_page() as new_page_info:
                page.locator('//a[contains(@href, "index-education.net/pronote/")]').click()
            pronote_page = new_page_info.value
            pronote_page.wait_for_load_state()

            try:
                pronote_page.click("text=Page d'accueil")
                pronote_page.wait_for_timeout(2000)
            except:
                pass

            elements = pronote_page.locator("div.ie-chips.gd-util-rouge-foncee").all()
            absences = []

            for elem in elements:
                try:
                    raison = elem.inner_text().strip()
                    cours_block = elem.evaluate_handle("el => el.closest('li.flex-contain')")

                    heure = cours_block.evaluate("""
                        el => {
                            const span = el.querySelector('span.sr-only');
                            if (!span) return "Heure inconnue";
                            const txt = span.innerText;
                            if (txt.includes("de") && txt.includes("à")) {
                                const h1 = txt.split("de")[1].split("à")[0].trim();
                                const h2 = txt.split("à")[1].trim();
                                return `${h1} → ${h2}`;
                            }
                            return "Heure inconnue";
                        }
                    """).strip()

                    matiere = cours_block.evaluate("""
                        el => {
                            const libelle = el.querySelector('.libelle-cours');
                            return libelle ? libelle.innerText.trim() : 'Matière inconnue';
                        }
                    """)

                    message = f"🕒 {heure} — 📘 {matiere} — ❌ {raison}"
                    if message not in absences_envoyees:
                        absences.append(message)
                        absences_envoyees.add(message)

                except Exception as e:
                    print(f"Erreur analyse cours : {e}")

            if absences:
                now = datetime.now().strftime('%d/%m/%Y à %Hh%M')
                contenu = f"🚨 Absences détectées le {now} :\n\n" + "\n".join(absences)
                envoyer_notification(contenu)
                print(contenu)
            elif not presence_envoyee:
                now = datetime.now().strftime('%d/%m/%Y à %Hh%M')
                envoyer_notification(f"✅ Tout le monde est présent le {now}.")
                presence_envoyee = True

        except Exception as e:
            print(f"❌ Erreur dans le robot : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    while True:
        lancer_robot()
        time.sleep(300)  # Attente de 5 minutes entre les vérifications