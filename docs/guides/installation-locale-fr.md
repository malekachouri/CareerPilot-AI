# Installer et tester CareerPilot AI en local (guide pas à pas)

## 0. Prérequis (une seule fois)

| Système | À installer |
|---------|-------------|
| **Windows 10/11** | [Git for Windows](https://git-scm.com/download/win) et Docker Desktop (gratuit pour un usage personnel), avec WSL 2 activé (Docker Desktop le propose à l'installation). |
| **macOS** | Git (`xcode-select --install`) et Docker Desktop, ou Colima / Rancher Desktop (open source). |
| **Linux** | `git` et Docker Engine avec le plugin Compose (`curl -fsSL https://get.docker.com \| sh`). |

Mémoire : environ **4 Go libres** sans IA, **10–12 Go** avec le modèle local (`qwen3:4b`). Disque : environ 10 Go.

Vérifier que tout est prêt :

```bash
git --version
docker compose version
```

## 1. Récupérer le code

```bash
git clone https://github.com/malekachouri/CareerPilot-AI.git
cd CareerPilot-AI
```

Si la dernière PR n'est pas encore fusionnée, testez sa branche : `git checkout claude/epic-allen-55qe9o`.
Une fois la PR fusionnée, restez sur `main` et faites `git pull` pour les mises à jour.

## 2. Configuration

```bash
cp .env.example .env
```

Sous Windows PowerShell : `Copy-Item .env.example .env`. Les valeurs par défaut conviennent pour un test local.

## 3. Démarrer

```bash
docker compose up -d --build --wait
```

Le premier démarrage prend 5 à 10 minutes : il construit les images, crée la base de données et charge les
catégories, les 55 questions, les 9 tests et la base de connaissances du coach.

- Application : **http://localhost:3000**. Créez un compte avec « Create an account ».
- Documentation de l'API : http://localhost:8000/api/v1/docs

Pour un compte administrateur (import de sources, file de relecture) :

```bash
docker compose run --rm api careerpilot create-admin --email vous@example.org
```

## 4. Activer l'IA locale (coach, générateur) — optionnel

```bash
docker compose --profile ai up -d
docker compose exec ollama ollama pull qwen3:4b
docker compose exec ollama ollama pull nomic-embed-text
docker compose run --rm api careerpilot kb-reindex
```

Sans IA, les tests, les statistiques et les QCM du coach fonctionnent. L'IA ajoute les explications détaillées,
les réponses ouvertes, les entretiens simulés, les indices, le tuteur et le générateur. Sur un CPU, une réponse
peut prendre de 20 secondes à 1 minute.

### Mémoire : choisir le bon modèle

L'IA tourne sur le processeur. Si elle n'a pas assez de RAM libre, elle utilise le disque (swap) et devient
des dizaines de fois plus lente. Le coach affiche alors « The local model took too long… ». Vérifiez avec
`free -h` (colonne *available*) :

| RAM disponible | Modèle conseillé (`LLM_MODEL` dans `.env`) | Qualité |
|----------------|--------------------------------------------|---------|
| ≥ 6 Go | `qwen3:4b` (défaut) | Bonne |
| 3–6 Go | `qwen3:1.7b` | Correcte |
| < 3 Go | `qwen3:0.6b` | Basique (tests seulement) |

Pour changer de modèle :

```bash
docker compose exec ollama ollama pull qwen3:1.7b
sed -i 's/^LLM_MODEL=.*/LLM_MODEL=qwen3:1.7b/' .env
docker compose up -d
```

Sous Windows (WSL), vous pouvez aussi donner plus de RAM à WSL : créez `C:\Users\<vous>\.wslconfig` avec
`[wsl2]` puis `memory=10GB` (sans dépasser ~75 % de la RAM du PC), lancez `wsl --shutdown` dans PowerShell et
redémarrez Docker Desktop. Fermer le navigateur et les applications lourdes libère aussi de la mémoire.

## 5. Importer vos tests privés (dépôt privé)

```bash
cd ..
git clone https://github.com/malekachouri/careerpilot-private-content.git
cd CareerPilot-AI
docker compose run --rm -v "$(pwd)/../careerpilot-private-content/captures:/private:ro" api careerpilot import-captures --owner vous@example.org --path /private
```

Sous Windows PowerShell, remplacez le chemin par le chemin complet, par exemple
`-v "C:\Users\vous\careerpilot-private-content\captures:/private:ro"`.
Le compte `--owner` doit déjà exister. Les questions restent visibles par vous seul (Companies → Neoshore…).

## 6. Que tester

1. **Tests** : lancez « Docker & Kubernetes », répondez, rechargez la page (la reprise fonctionne), soumettez,
   puis lisez les explications.
2. **Coach** : « DevOps Interview Agent », répondez à un QCM, demandez un indice, posez une question au tuteur.
   Avec l'IA : « System Design Agent » (réponse ouverte notée par critère), « Coding Interview Agent » (éditeur de
   code), puis un entretien « Technical interview » jusqu'au rapport.
3. **Analytics** : niveau par sujet, lacunes, erreurs répétées.
4. **Tests → Import my questions** : importez un fichier JSON, CSV, Markdown ou PDF de questions.

## 7. Arrêter, mettre à jour, réinitialiser

```bash
docker compose down                          # arrête (les données sont conservées)
git pull && docker compose up -d --build --wait   # met à jour
docker compose down -v                       # ⚠ supprime aussi toutes les données
```

## Dépannage

| Problème | Solution |
|----------|----------|
| Port 3000 ou 8000 déjà utilisé | Mettez `WEB_PORT=3001` dans `.env`. Pour 8000 ou 5432, arrêtez l'autre programme. |
| Un service ne démarre pas | `docker compose ps`, puis `docker compose logs -f api worker web` |
| « Local model not available » | Lancez l'étape 4, et vérifiez avec `docker compose exec ollama ollama list` |
| Le coach reste sur « thinking… » ou « took too long » | Manque de RAM (voir « Mémoire » ci-dessus). Suivez `docker compose logs -f worker-ai`. |
| Windows : Docker très lent | Gardez le projet dans le système de fichiers WSL (`\\wsl$\...`) plutôt que dans `C:\` |
