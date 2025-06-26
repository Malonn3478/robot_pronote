from playwright.sync_api import sync_playwright
import requests
from datetime import datetime
import os
import time

USERNAME = os.getenv("ENT_USERNAME")
PASSWORD = os.getenv("ENT_PASSWORD")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

absences_envoyees = set()
presence_envoyee = False

def envoyer_notification(message):
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print(f"Erreur d'envoi Discord : {e}")

def lancer_robot():
    global presence_envoyee
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            # Connexion ENT
            page.goto("https://cas.mon-ent-occitanie.fr/login?service=https%3A%2F%2Fwww.mon-ent-occitanie.fr%2Fsg.do%3FPROC%3DIDENTIFICATION_FRONT")
            page.click("//button[contains(., 'ou parent')]")
            page.click('//label[@for="idp-MONT-EDU_parent_eleve"]')
            page.click('//input[@id="button-submit"]')
            page.wait_for_selector('//button[@id="bouton_eleve"]', timeout=10000)
            page.click('//button[@id="bouton_eleve"]')
            page.fill('//input[@id="username"]', USERNAME)
            page.fill('//input[@id="password"]', PASSWORD)
            page.click('//button[@id="bouton_valider"]')
            page.wait_for_timeout(2000)

            # Accès à Pronote
            page.evaluate("""
                let span = [...document.querySelectorAll('span')].find(e => e.textContent.includes('Site inter-établissements'));
                if (span) span.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            """)
            page.click("text=LYCEE JEAN MOULIN")
            page.goto("https://jean-moulin-beziers.mon-ent-occitanie.fr/sg.do?PROC=PAGE_ACCUEIL&ACTION=VALIDER")

            with context.expect_page() as popup:
                page.click("a[href*='index-education.net/pronote/']")
            pronote = popup.value
            pronote.wait_for_load_state()

            try:
                pronote.click("text=Page d'accueil")
                pronote.wait_for_timeout(2000)
            except:
                pass

            blocs = pronote.locator("div.ie-chips.gd-util-rouge-foncee").all()
            absences = []

            for bloc in blocs:
                try:
                    raison = bloc.inner_text().strip()
                    parent = bloc.evaluate_handle("el => el.closest('li.flex-contain')")

                    heure = parent.evaluate("""
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

                    matiere = parent.evaluate("""
                        el => {
                            const lib = el.querySelector('.libelle-cours');
                            return lib ? lib.innerText.trim() : 'Matière inconnue';
                        }
                    """)

                    message = f"🕒 {heure} — 📘 {matiere} — ❌ {raison}"
                    if message not in absences_envoyees:
                        absences.append(message)
                        absences_envoyees.add(message)

                except Exception as e:
                    print(f"Erreur d’analyse : {e}")

            if absences:
                now = datetime.now().strftime("%d/%m/%Y à %Hh%M")
                contenu = f"🚨 Absences détectées le {now} :\n\n" + "\n".join(absences)
                envoyer_notification(contenu)
                print(contenu)
            elif not presence_envoyee:
                now = datetime.now().strftime("%d/%m/%Y à %Hh%M")
                envoyer_notification(f"✅ Tout le monde est présent le {now}.")
                presence_envoyee = True

        except Exception as e:
            print(f"❌ Erreur robot : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    while True:
        lancer_robot()
        time.sleep(300)  # Toutes les 5 minutes