# Guide de l'oral · PitWall Analytics

Durée visée : **15 minutes de présentation + 5 minutes de démo**, puis questions.
Deux voix : **P1 = ingestion & plateforme**, **P2 = modélisation & produit**. On alterne toutes les 2-3 slides.

## L'histoire en 4 phrases (à savoir par cœur, tous les deux)
1. PitWall Analytics (entreprise fictive) vend des prédictions F1 aux joueurs de fantasy et aux médias.
2. Chaque jour à 7 h (Paris), Airflow lance 5 ingestions (5 vraies sources, 5 méthodes) vers Snowflake.
3. dbt nettoie (silver), teste, puis construit un modèle en étoile et une table par cas d'usage (gold).
4. Une régression logistique prédit le podium du prochain Grand Prix (São Paulo, 8 novembre 2026), affiché
   dans Streamlit ; elle apprend sur toutes les courses passées, mais chaque saison plus ancienne compte
   deux fois moins (nouvelles voitures en 2026).

## Déroulé slide par slide

| # | Slide | Qui | Temps | Ce qu'il faut dire (l'essentiel) | Critère |
|---|---|---|---|---|---|
| 1 | PitWall Analytics | P1 | 0:30 | « On prédit le podium F1 avant le départ. Prochaine course : São Paulo, 8 novembre. » | C8 |
| 2 | Two engineers, one pipeline | P1 | 0:45 | Qui fait quoi ; clients (fantasy B2C, médias B2B) ; contraintes : 2 h après les qualifs, ≤ 10 crédits/mois. | C1 |
| 3 | Five use cases | P2 | 1:30 | Pour chaque cas : utilisateur → décision, métrique et grain, fréquence, test d'acceptation. | C2 |
| 4 | Five real sources | P1 | 1:00 | 5 sources, 5 modes : API incrémentale, batch CSV, API météo, librairie Python, fichier statique. | C3 |
| 5 | How we predict São Paulo | P2 | 1:15 | Les 6 entrées les plus récentes ; pondération ×1 / ×0,5 / ×0,25 ; refaite après chaque séance. | C2, C3 |
| 6 | One pipeline, five use cases | P1 | 1:30 | Suivre les numéros 1 → 8 ; Airflow orchestre, Terraform crée l'infra, quarantaine pour les lignes impossibles. | C3, C5 |
| 7 | What each step does | P1 → P2 | 1:15 | Une garantie par étape : retry, MERGE, traçabilité bronze, tests dbt, backtest, rôle lecture seule. | C3, C6 |
| 8 | Tools | P2 | 1:00 | Un outil par besoin et pourquoi pas l'alternative ; Kafka écarté (batch suffit). | C4 |
| 9 | OLAP, not OLTP | P2 | 0:45 | On lit beaucoup d'historique, on écrit par lots → entrepôt colonnes + étoile. | C4 |
| 10 | Gold star schema | P2 | 0:45 | Fait = course × pilote (testé unique) ; 5 dimensions. | C3 |
| 11 | Scale and cost | P1 | 1:00 | ≈ 7 crédits ≈ 20 €/mois ; ×10 clients ≈ 90 €/mois ; le coût suit les lecteurs, pas les données ; alerte à 10 crédits. | C7 |
| 12 | Trends (45 races) | P2 | 1:00 | 60 % des courses gagnées depuis la pole (27/45), 80 % des vainqueurs partent de la 1ʳᵉ ligne, Haas +3,0 places en 2025. | C2, C8 |
| 13 | Live demo | P1 + P2 | 5:00 | Voir « Démo » ci-dessous. | C5, C6 |
| 14 | Questions? | P1 | 0:15 | Lien GitHub, merci. | C8 |

## Démo live (5 minutes)
1. **P1** · Airflow → `pitwall_daily` → *Trigger* → vue *Graph* qui passe au vert.
2. **P2** · Snowsight → `GOLD.UC1_PODIUM_PREDICTIONS` : le top 3 pour São Paulo ; `GOLD.UC1_MODEL_BACKTEST`.
3. **P1** · Incident A : *Trigger DAG w/ config* `{"simulate_outage": "1"}` → tâche rouge, 2 retries, alerte Slack.
4. **P2** · Incident C : `sql/03_incident_drills.sql` (deux vainqueurs) → `dbt build` échoue sur
   `assert_one_winner_per_race`, gold n'est pas mis à jour.
5. **P1** · Accès : `sql/01_access_check.sql` → GOLD autorisé, BRONZE refusé.

Plan B : la vidéo enregistrée des mêmes étapes (2 minutes).

## Les chiffres à connaître
| Chiffre | Valeur | Où le prouver |
|---|---|---|
| Backtest 2025 (entraîné sur 2024) | modèle **79,4 %** des podiums trouvés vs **76,2 %** pour la grille, 21 courses | `pytest tests -s` |
| Courses analysées (slide 12) | 45 (24 en 2024, 21 en 2025 jusqu'à São Paulo 2025) | `tests/data/` |
| Victoires depuis la pole | 27 / 45 = 60 % | idem |
| Vainqueurs en 1ʳᵉ ligne | 36 / 45 = 80 % | idem |
| Bug FastF1 corrigé | 530 des 575 pilotes classés avaient un écart, pas un temps total | `stg_fastf1_results.sql` |
| Coût | ≈ 7 crédits ≈ 20 €/mois ; ×10 clients ≈ 30 crédits ≈ 90 €/mois | `docs/costs_and_security.md` |
| Budget | moniteur à 10 crédits/mois : e-mail à 50 % et 80 %, suspension à 100 % | `sql/02_budget_monitor.sql` |

## Les mots du cours à placer
| Mot | Où dans le code | En une phrase |
|---|---|---|
| bronze / silver / gold | `dbt/pitwall_dbt/models` | tel que reçu → typé, nettoyé, dédoublonné → prêt pour la décision |
| watermark (incrémental) | `ingest_jolpica.py` | on repart de la dernière manche chargée et on la recharge (pénalités d'après course) |
| MERGE / idempotent | `common.py` | relancer deux fois = même résultat, jamais de doublon |
| quarantaine | `results_quarantine.sql` | les lignes impossibles sont mises de côté avec leur raison, pas supprimées |
| test de clé / règle métier / complétude / fraîcheur | `schema.yml`, `tests/`, `sources.yml` | grain unique ; un seul vainqueur ; résultats présents 2 jours après ; bronze < 30 h |
| date du run | DAG `{{ ds }}`, macro `run_date()` | jamais « aujourd'hui » en dur : les rattrapages marchent |
| moindre privilège | `terraform/main.tf`, `sql/01_access_check.sql` | le dashboard lit GOLD, pas BRONZE |
| state Terraform protégé | `.gitignore`, `backend.tf.example` | jamais dans Git, distant, versionné, verrouillé |
| OLAP | Snowflake, modèle en étoile | beaucoup de lectures d'historique, écritures par lots |

## Questions probables du jury (et réponse courte)
- **Pourquoi pas du streaming ?** Les décisions sont prises une fois par séance ; un batch quotidien + un run
  après chaque séance suffit. Kafka ajouterait du coût et de l'exploitation sans changer une seule décision.
- **Quelle version gagne si un résultat existe deux fois ?** Jolpica avant Kaggle, puis le dernier `_loaded_at`,
  puis un départage fixe (`constructor_ref`) : c'est déterministe.
- **Réparer, NULL ou quarantaine ?** On répare si la règle est sûre (temps FastF1 = temps du vainqueur + écart),
  NULL pour `\N`, quarantaine si la ligne fausserait un chiffre (course inconnue, position impossible).
- **Fuseau horaire ?** Tout en UTC ; la date de run est en Europe/Paris, le fuseau de l'entreprise.
- **Fuite de données dans le modèle ?** Non : la forme ne regarde que les courses **avant** celle prédite.
- **Pourquoi une régression logistique ?** Un poids par entrée, facile à expliquer ; ~24 courses par an,
  c'est peu de données pour du gradient boosting.
- **Que se passe-t-il si l'API tombe ?** 2 retries à 5 minutes, puis alerte Slack ; le run suivant rattrape
  grâce au watermark.
- **Et si on charge deux fois le même jour ?** Mêmes comptages avant/après : MERGE sur la clé métier + dédoublonnage.
- **Comment le coût évolue avec ×10 clients ?** Seul l'entrepôt du dashboard grandit (lecteurs) ; le stockage
  reste minuscule.
- **Données personnelles ?** Données publiques, mais les pilotes sont des personnes : on ne garde que l'année
  de naissance dans gold.

## Les limites à dire avant qu'on nous les demande
- Règlement 2026 : nouvelles voitures, l'historique prédit moins bien (d'où la pondération des saisons récentes).
- Pénalités de grille connues seulement avec la grille officielle ; abandons imprévisibles.
- FastF1 n'existe que depuis 2018 : le cas d'usage 5 couvre les 5 dernières saisons.

## À faire vous-mêmes avant l'oral
- Remplacer `[Name]` (slide 2) et `[your-account]` (slide 14 et README) par vos vrais noms et compte GitHub.
- `terraform apply`, construire les deux images, lancer `pitwall_backfill` puis `pitwall_daily`.
- Noter le chiffre du backtest 2026 (`GOLD.UC1_MODEL_BACKTEST`) et les crédits réellement consommés.
- Enregistrer la vidéo de secours de la démo.
- Pousser le repo sur GitHub (sans `.env`, `.p8`, `terraform.tfvars`, ni state).
