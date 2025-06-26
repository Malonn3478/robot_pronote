from playwright.sync_api import sync_playwright
import requests
from datetime import datetime
import time

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/TON_WEBHOOK_ICI"

# Mémoriser les absences déjà signalées
absences_signalees = set()
tout_le_monde_present_envoye = False

def envoyer_notification_discord(message):
    payload = {"content": message}
    response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    print(f"📣 Notification envoyée ! Code HTTP : {response.status_code}")

def detecter_absences():
    global tout_le_monde_present_envoye
    nouvelles_absences = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True, args=["--start-maximized"])
            context = browser.new_context(no_viewport=True)
            page = context.new_page()

            # Connexion ENT
            page.goto("https://cas.mon-ent-occitanie.fr/login?service=https%3A%2F%2Fwww.mon-ent-occitanie.fr%2Fsg.do%3FPROC%3DIDENTIFICATION_FRONT")
            page.locator("//button[text()[contains(.,'ou parent')]]").click()
            page.locator('//label[@for="idp-MONT-EDU_parent_eleve"]').click()
            page.locator('//input[@id="button-submit"]').click()
            page.wait_for_selector('//button[@id="bouton_eleve"]', state="visible")
            page.locator('//button[@id="bouton_eleve"]').click()
            page.fill('//input[@id="username"]', 'TON_IDENTIFIANT')
            page.fill('//input[@id="password"]', 'TON_MOT_DE_PASSE')
            page.click('//button[@id="bouton_valider"]')
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)

            # Clic sur "Site inter-établissements"
            page.evaluate("""
                const span = Array.from(document.querySelectorAll('span')).find(
                    e => e.textContent.includes('Site inter-établissements')
                );
                if (span) {
                    span.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                }
            """)

            # Accès au lycée
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

            print("✅ Page chargée, détection des cours...")

            elements = pronote_page.locator("div.ie-chips.gd-util-rouge-foncee").all()

            for elem in elements:
                try:
                    raison = elem.inner_text().strip()
                    cours_block = elem.evaluate_handle("el => el.closest('li.flex-contain')")

                    # Heure
                    plage_text = cours_block.evaluate("""
                        el => {
                            const span = el.querySelector('span.sr-only');
                            return span ? span.innerText : '';
                        }
                    """).strip()

                    if "de" in plage_text and "à" in plage_text:
                        heure_debut = plage_text.split("de")[1].split("à")[0].strip()
                        heure_fin = plage_text.split("à")[1].strip()
                        heure = f"{heure_debut} → {heure_fin}"
                    else:
                        heure = "Heure inconnue"

                    # Matière
                    matiere = cours_block.evaluate("""
                        el => {
                            const libelle = el.querySelector('.libelle-cours');
                            return libelle ? libelle.innerText.trim() : 'Matière inconnue';
                        }
                    """)

                    message = f"🕒 {heure} — 📘 {matiere} — ❌ {raison}"

                    if message not in absences_signalees:
                        nouvelles_absences.append(message)
                        absences_signalees.add(message)

                except Exception as e:
                    print(f"⚠️ Erreur lors de l’analyse d’un cours : {e}")

            if nouvelles_absences:
                maintenant = datetime.now().strftime('%d/%m/%Y à %Hh%M')
                message = f"🚨 Absences détectées le {maintenant} :\n\n" + "\n".join(nouvelles_absences)
                envoyer_notification_discord(message)
                tout_le_monde_present_envoye = False
            elif not tout_le_monde_present_envoye:
                envoyer_notification_discord("✅ Tout le monde est présent aujourd'hui !")
                tout_le_monde_present_envoye = True

            browser.close()

    except Exception as e:
        print(f"❌ Erreur dans le robot : {e}")

# Boucle infinie
if __name__ == "__main__":
    while True:
        detecter_absences()
        print("🔁 Nouvelle vérification dans 5 minutes...")
        time.sleep(300)  # 5 minutes