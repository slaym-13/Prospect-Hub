# Prospect Suite

Plateforme de recherche, d'analyse et de candidature aux opportunités
professionnelles à Marrakech.

Le projet part de 283 entreprises collectées via l'API Google Places et va jusqu'à
l'envoi d'une candidature spontanée et au suivi de la réponse : collecte →
exploration → nettoyage en Python → analyse → application web.

| Dossier | Contenu |
|---|---|
| [`app/`](app/) | La plateforme : serveur Python (Flask 3), client React 19 + Vite + Tailwind |
| [`analysis/`](analysis/) | La chaîne de traitement Python : exploration, nettoyage, analyse |
| [`presentation/`](presentation/) | La présentation du projet et le script Python (python-pptx) qui la génère |
| [`docs/`](docs/) | Historique et notes du prototype initial |

---

## 1. Installation

Prérequis : **Python 3.10 ou plus** et pip. **Node.js 20.19 ou plus** sert uniquement à
construire l'interface React ; il n'est pas nécessaire pour faire tourner le serveur.

```bash
git clone https://github.com/slaym-13/Prospect-Suite.git
cd Prospect-Suite
```

### La plateforme

```bash
cd app
python -m venv .venv
source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # voir la configuration ci-dessous
npm install && npm run build  # construit le client React dans app/dist
python server.py            # http://127.0.0.1:3000
```

Le jeu de données fait partie de l'application : les 283 entreprises de
`app/data/companies.csv` sont chargées toutes seules au premier démarrage, il n'y a
rien à importer.

### Le compte administrateur

Au démarrage, si la base ne contient aucun compte, l'application en crée un à partir
de `ADMIN_EMAIL` et `ADMIN_PASSWORD` :

```bash
ADMIN_EMAIL=vous@exemple.com ADMIN_PASSWORD='un mot de passe long' python server.py
```

Sans ces variables, un compte de développement est créé avec des identifiants par
défaut, et le serveur l'annonce dans la console au premier démarrage. Ces identifiants
sont destinés au poste local uniquement.

> **En production, `ADMIN_PASSWORD` est obligatoire.** Les identifiants par défaut sont
> lisibles dans le code source : toute instance accessible publiquement qui les
> conserve est ouverte à n'importe qui. Le serveur affiche un avertissement tant
> qu'ils sont en usage.

Chacun peut créer son propre compte depuis la page de connexion : **Créer un compte**
demande une adresse, un mot de passe d'au moins 10 caractères, et la confirmation de
ce mot de passe. Les comptes créés ainsi sont toujours des utilisateurs ordinaires. Un
administrateur peut fermer les inscriptions depuis la page Admin, ce qui masque aussi
le lien.

Les comptes peuvent aussi être créés depuis la page **Admin**, ou en ligne de commande :

```bash
python scripts/create_user.py collegue@exemple.com "un mot de passe assez long"
```

### La chaîne d'analyse

```bash
pip install pandas matplotlib numpy
cd analysis
python 01_explore.py        # profil du fichier brut   -> outputs/exploration.json
python 02_clean.py          # nettoyage                -> outputs/companies_clean.csv
python 03_analyze.py        # analyse + 10 figures     -> outputs/analysis.json
```

### La présentation

```bash
pip install python-pptx
python presentation/build_deck.py   # depuis la racine -> presentation/deck_generated.pptx
```

Le script reprend les figures de `analysis/outputs/figures`. La version finale,
`IOADA202_HARMACH_SOULAIMANE_VF.pptx`, a été retouchée à la main ; le script écrit
donc dans un autre fichier pour ne jamais l'écraser (`--out` pour choisir).

---

## 2. Configuration

Tout est optionnel : l'application fonctionne sans aucune clé. Les variables se
placent dans `app/.env` (modèle fourni dans [`app/.env.example`](app/.env.example)).

| Variable | Rôle | Sans elle |
|---|---|---|
| `SESSION_SECRET` | 24+ caractères aléatoires, garde les sessions valides entre deux redémarrages | une clé est générée dans `app/data/.secret` |
| `PORT`, `HOST` | écoute du serveur (défaut `127.0.0.1:3000`) | valeurs par défaut |
| `GEMINI_MODEL` | modèle utilisé par les clés des utilisateurs (défaut `gemini-2.5-flash`) | `gemini-2.5-flash` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM_EMAIL` | envoi réel des emails | **l'envoi est désactivé** |
| `SMTP_MODE=json` | mode test : les messages sont journalisés, jamais livrés | — |
| `GOOGLE_PLACES_API_KEY` | complète les sites web et téléphones manquants | le bouton n'apparaît pas |
| `TRUST_PROXY` | à mettre à `true` derrière un reverse proxy HTTPS | — |

**La clé d'IA n'est pas une variable d'environnement.** Chaque utilisateur saisit sa
propre clé **Google Gemini** dans *Réglages → AI* (gratuite sur
[aistudio.google.com/apikey](https://aistudio.google.com/apikey)). Elle est vérifiée
auprès de Google, chiffrée en AES-256-GCM avant stockage, et jamais renvoyée au
navigateur.

---

## 3. Exécution

| Commande (dans `app/`) | Effet |
|---|---|
| `python server.py` | sert l'API et le client déjà construit (serveur waitress) |
| `python server.py --reload` | API Flask en mode développement, redémarre à chaque modification d'un fichier `.py` |
| `npm run dev` | serveur Vite avec rechargement à chaud, sur le port 5173 (à lancer en parallèle de l'API) |
| `npm run build` | construit le client dans `app/dist` |
| `python -m pytest` | 15 tests de bout en bout, sans accès internet |
| `python scripts/create_user.py` | crée un compte depuis le terminal |
| `python enrich.py companies.json` | vérificateur de sites web, optionnel |

En développement, ouvrez **http://127.0.0.1:5173** (Vite relaie `/api` vers le port
3000). En production, `python server.py` sert tout sur un seul port.

---

## 4. Ce que fait la plateforme

- **Tableau de bord** — indicateurs et 4 graphiques Chart.js, filtrables, chacun
  doublé d'une vue tableau.
- **Aujourd'hui** — les relances dues, puis les meilleurs prospects du jour classés
  par score d'opportunité.
- **Entreprises** — les 283 fiches : recherche, filtres, tri et export CSV.
- **Pipeline** — tableau kanban. Chaque colonne défile indépendamment, donc le
  tableau tient sur un écran ; le plateau défile horizontalement pour atteindre les
  dernières colonnes. Glisser-déposer ou menu sur la carte, filtre global, relances
  en retard en tête de colonne.
- **Panneau entreprise** — contact (Appel, WhatsApp, Email, Maps, Site), score
  détaillé, rédaction assistée par IA, envoi, journal des contacts, audit du site.
- **Admin** — réservé aux administrateurs, l'onglet est masqué pour les autres.
  Gestion des comptes (ajouter, changer un mot de passe, accorder ou retirer les
  droits, supprimer, ouvrir ou fermer les inscriptions) et des fiches entreprise (corriger le nom, la catégorie,
  l'adresse, le téléphone, l'email, le site, la note, le nombre d'avis ; ajouter ou
  supprimer une entreprise ; recharger le jeu de données livré).
- **Réglages** — identité de l'expéditeur, plafond d'envoi, clé IA, pondérations du
  score (avec le nombre d'entreprises par palier qui se recalcule pendant qu'on
  déplace un curseur) et paliers par secteur, réglés en cinq boutons.
- **Assistant « Ask »** — répond aux questions sur l'application à partir d'un guide
  interne, d'un instantané des données de l'utilisateur et de l'historique de la
  conversation.

### Le score d'opportunité

Chaque entreprise reçoit une note de 0 à 100 à partir de quatre facteurs pondérés :
secteur d'activité (30), absence de site web (30), volume d'avis Google (25),
joignabilité téléphonique (15). Les pondérations se modifient dans les réglages et
tous les classements se recalculent immédiatement.

La formule est implémentée deux fois — en Python dans
[`analysis/03_analyze.py`](analysis/03_analyze.py) pour le rapport, et dans le
navigateur dans [`app/client/src/lib/scoring.js`](app/client/src/lib/scoring.js) pour
que les classements se recalculent instantanément — avec les mêmes poids, afin que les
chiffres du rapport et ceux de l'application ne divergent jamais.

---

## 5. La démarche data

Détail complet dans [`analysis/README.md`](analysis/README.md).

**Problèmes détectés** sur le fichier brut : 50 % des entreprises sans email, le
libellé « Services » couvrant 51 % du fichier, 34 notes de 5,0/5 obtenues sur 3 avis
ou moins, 59 sites en `http://`, un doublon, une géolocalisation hors zone, et un
BOM UTF-8 qui rend la première colonne illisible sans `encoding="utf-8-sig"`.

**Corrections appliquées** : déduplication, normalisation des téléphones au format
marocain, normalisation des URLs, validation des emails, note pondérée par le nombre
d'avis (m-estimate), secteur re-dérivé du nom quand le libellé est générique.
Chaque correction est comptée dans `outputs/cleaning_report.json`.

**Deux choix assumés** : une note manquante n'est jamais remplacée par la moyenne
(une note inventée fausserait le classement des prospects), et la note pondérée
corrige les 5,0 parfaits issus d'échantillons minuscules — justifiée par une
corrélation mesurée de **−0,32** entre le nombre d'avis et la note.

**Résultats** : 97 % des entreprises sont joignables par téléphone, 70 % par
WhatsApp, mais seulement 50 % par email ; 22 % n'ont aucun site web ; 68 entreprises
sur 282 dépassent 65/100 et constituent la cible prioritaire.

---

## 6. Sécurité et usage responsable

Côté serveur (Python) : les mots de passe sont hachés avec bcrypt, les sessions sont des cookies HttpOnly
signés, les tentatives de connexion sont limitées, les requêtes modifiantes exigent
un en-tête spécifique, et une CSP stricte est appliquée.

L'envoi d'emails non sollicités à des entreprises est encadré (loi 09-08 au Maroc,
RGPD pour des destinataires européens). L'application ajoute une ligne de
désinscription et un en-tête `List-Unsubscribe` à chaque message, applique un
plafond quotidien, refuse de réécrire au même contact sous 14 jours et bloque tout
contact marqué « ne pas contacter ». **Relisez chaque brouillon : un texte rédigé
par IA peut être faux.**

---

## 7. Données

`app/data/companies.csv` contient 283 entreprises de Marrakech collectées via
l'API Google Places (14 requêtes croisant un métier et la ville, dédupliquées par
`place_id`). Ce sont des informations professionnelles publiques.

Ce fichier est **livré avec le code** et chargé au démarrage si la base est vide :
l'application n'a donc pas d'écran d'import, et elle affiche ses données même sur un
hébergement dont le disque est réinitialisé à chaque déploiement. Pour modifier le
jeu de données, on édite le CSV et on redéploie.

Les données d'exécution (`db.json`, `users.json`, `.secret`) ne sont volontairement
pas versionnées.
