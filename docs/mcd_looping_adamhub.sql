-- ============================================================
-- AdamHUB - Schéma relationnel exporté depuis Looping (MLD)
-- Modélisation selon le cours de M. Franck Ravat (IRIT / UT1)
-- ============================================================

-- ------------------------------------------------------------
-- 1. TABLES ISSUES DES CLASSES D'ENTITÉS (Règle R1 & R2)
-- ------------------------------------------------------------

CREATE TABLE UTILISATEUR(
   CodeUser INT,
   EmailUser VARCHAR(255) NOT NULL,
   NomUser VARCHAR(100) NOT NULL,
   DateCreationUser DATETIME NOT NULL,
   EstActifUser LOGICAL NOT NULL DEFAULT TRUE,
   NotesNutrition TEXT,
   PRIMARY KEY(CodeUser)
);

CREATE TABLE FAIT_MEMOIRE(
   CodeMemoire INT,
   CategorieFait VARCHAR(50) NOT NULL,
   ContenuFait VARCHAR(500) NOT NULL,
   CodeUser INT NOT NULL,
   PRIMARY KEY(CodeMemoire),
   FOREIGN KEY(CodeUser) REFERENCES UTILISATEUR(CodeUser)
);

CREATE TABLE REGIME_ALIMENTAIRE(
   CodeRegime INT,
   LibelleRegime VARCHAR(50) NOT NULL,
   PRIMARY KEY(CodeRegime)
);

CREATE TABLE UNITE_MESURE(
   CodeUnite VARCHAR(10),
   LibelleUnite VARCHAR(50) NOT NULL,
   TypeGrandeur VARCHAR(30) NOT NULL,
   PRIMARY KEY(CodeUnite)
);

CREATE TABLE INGREDIENT(
   CodeIng INT,
   NomIng VARCHAR(150) NOT NULL,
   RayonIng VARCHAR(50),
   CodeUnite VARCHAR(10) NOT NULL,
   PRIMARY KEY(CodeIng),
   FOREIGN KEY(CodeUnite) REFERENCES UNITE_MESURE(CodeUnite)
);

CREATE TABLE ENSEIGNE(
   CodeEnseigne VARCHAR(20),
   NomEnseigne VARCHAR(50) NOT NULL,
   PRIMARY KEY(CodeEnseigne)
);

CREATE TABLE MAGASIN(
   CodeMagasin INT,
   NomMagasin VARCHAR(150) NOT NULL,
   AdresseMagasin VARCHAR(255) NOT NULL,
   TypeRetrait VARCHAR(30) NOT NULL,
   CodeEnseigne VARCHAR(20) NOT NULL,
   PRIMARY KEY(CodeMagasin),
   FOREIGN KEY(CodeEnseigne) REFERENCES ENSEIGNE(CodeEnseigne)
);

CREATE TABLE PANIER_DRIVE(
   CodePanier INT,
   DateCreationPanier DATETIME NOT NULL,
   StatutPanier VARCHAR(30) NOT NULL,
   CodeUser INT NOT NULL,
   CodeMagasin INT NOT NULL,
   PRIMARY KEY(CodePanier),
   FOREIGN KEY(CodeUser) REFERENCES UTILISATEUR(CodeUser),
   FOREIGN KEY(CodeMagasin) REFERENCES MAGASIN(CodeMagasin)
);

CREATE TABLE USTENSILE(
   CodeUst INT,
   NomUst VARCHAR(100) NOT NULL,
   PRIMARY KEY(CodeUst)
);

CREATE TABLE RECETTE(
   CodeRecette INT,
   NomRecette VARCHAR(150) NOT NULL,
   DescriptionRec TEXT,
   NbPortionsBase INT NOT NULL DEFAULT 1,
   TempsPrepMin INT NOT NULL DEFAULT 0,
   TempsCuissonMin INT NOT NULL DEFAULT 0,
   CodeUser INT,
   PRIMARY KEY(CodeRecette),
   FOREIGN KEY(CodeUser) REFERENCES UTILISATEUR(CodeUser)
);

CREATE TABLE ETAPE(
   CodeEtape INT,
   NumOrdreEtape INT NOT NULL,
   ConsigneEtape TEXT NOT NULL,
   DureeEtapeMin INT NOT NULL DEFAULT 0,
   CodeRecette INT NOT NULL,
   PRIMARY KEY(CodeEtape),
   FOREIGN KEY(CodeRecette) REFERENCES RECETTE(CodeRecette)
);

CREATE TABLE TAG(
   CodeTag INT,
   LibelleTag VARCHAR(50) NOT NULL,
   PRIMARY KEY(CodeTag)
);

CREATE TABLE LISTE_COURSES(
   CodeListe INT,
   NomListe VARCHAR(100) NOT NULL,
   DateCreationListe DATETIME NOT NULL,
   StatutListe VARCHAR(30) NOT NULL,
   CodeUser INT NOT NULL,
   PRIMARY KEY(CodeListe),
   FOREIGN KEY(CodeUser) REFERENCES UTILISATEUR(CodeUser)
);

CREATE TABLE REPAS_PLANIFIE(
   CodeRepasPlanif INT,
   DateRepas DATE NOT NULL,
   CreneauRepas VARCHAR(20) NOT NULL,
   NbPortionsPlanif INT NOT NULL DEFAULT 1,
   EstCuisinee LOGICAL NOT NULL DEFAULT FALSE,
   DateCuissonReelle DATETIME,
   CodeRecette INT NOT NULL,
   CodeUser INT NOT NULL,
   PRIMARY KEY(CodeRepasPlanif),
   FOREIGN KEY(CodeRecette) REFERENCES RECETTE(CodeRecette),
   FOREIGN KEY(CodeUser) REFERENCES UTILISATEUR(CodeUser)
);

CREATE TABLE PRODUIT_MAGASIN(
   CodeProduitMag INT,
   RefArticleMag VARCHAR(50) NOT NULL,
   NomProduitMag VARCHAR(255) NOT NULL,
   MarqueProduit VARCHAR(100),
   Conditionnement VARCHAR(100) NOT NULL,
   PrixVenteActuel REAL NOT NULL,
   CodeIng INT,
   CodeEnseigne VARCHAR(20) NOT NULL,
   PRIMARY KEY(CodeProduitMag),
   FOREIGN KEY(CodeIng) REFERENCES INGREDIENT(CodeIng),
   FOREIGN KEY(CodeEnseigne) REFERENCES ENSEIGNE(CodeEnseigne)
);

-- ------------------------------------------------------------
-- 2. TABLES ISSUES DES ASSOCIATIONS N-N & PORTEUSES (Règle R3)
-- ------------------------------------------------------------

CREATE TABLE Adopter_Regime(
   CodeUser INT,
   CodeRegime INT,
   PRIMARY KEY(CodeUser, CodeRegime),
   FOREIGN KEY(CodeUser) REFERENCES UTILISATEUR(CodeUser),
   FOREIGN KEY(CodeRegime) REFERENCES REGIME_ALIMENTAIRE(CodeRegime)
);

CREATE TABLE Contenir_Panier(
   CodePanier INT,
   CodeProduitMag INT,
   QuantitePanier INT NOT NULL DEFAULT 1,
   PRIMARY KEY(CodePanier, CodeProduitMag),
   FOREIGN KEY(CodePanier) REFERENCES PANIER_DRIVE(CodePanier),
   FOREIGN KEY(CodeProduitMag) REFERENCES PRODUIT_MAGASIN(CodeProduitMag)
);

CREATE TABLE Necessiter(
   CodeRecette INT,
   CodeUst INT,
   PRIMARY KEY(CodeRecette, CodeUst),
   FOREIGN KEY(CodeRecette) REFERENCES RECETTE(CodeRecette),
   FOREIGN KEY(CodeUst) REFERENCES USTENSILE(CodeUst)
);

CREATE TABLE Classifier(
   CodeRecette INT,
   CodeTag INT,
   PRIMARY KEY(CodeRecette, CodeTag),
   FOREIGN KEY(CodeRecette) REFERENCES RECETTE(CodeRecette),
   FOREIGN KEY(CodeTag) REFERENCES TAG(CodeTag)
);

CREATE TABLE Contenir_Course(
   CodeListe INT,
   CodeIng INT,
   QuantiteAcheter REAL NOT NULL,
   EstAchete LOGICAL NOT NULL DEFAULT FALSE,
   PRIMARY KEY(CodeListe, CodeIng),
   FOREIGN KEY(CodeListe) REFERENCES LISTE_COURSES(CodeListe),
   FOREIGN KEY(CodeIng) REFERENCES INGREDIENT(CodeIng)
);

CREATE TABLE Composer(
   CodeRecette INT,
   CodeIng INT,
   QuantiteNecessaire REAL NOT NULL,
   NotePreparation VARCHAR(255),
   PRIMARY KEY(CodeRecette, CodeIng),
   FOREIGN KEY(CodeRecette) REFERENCES RECETTE(CodeRecette),
   FOREIGN KEY(CodeIng) REFERENCES INGREDIENT(CodeIng)
);

CREATE TABLE Stocker_GardeManger(
   CodeUser INT,
   CodeIng INT,
   QuantiteEnStock REAL NOT NULL DEFAULT 0,
   SeuilMinStock REAL NOT NULL DEFAULT 0,
   DatePeremption DATE,
   EmplacementStock VARCHAR(50),
   PRIMARY KEY(CodeUser, CodeIng),
   FOREIGN KEY(CodeUser) REFERENCES UTILISATEUR(CodeUser),
   FOREIGN KEY(CodeIng) REFERENCES INGREDIENT(CodeIng)
);

CREATE TABLE Choisir_Drive(
   CodeUser INT,
   CodeMagasin INT,
   PRIMARY KEY(CodeUser, CodeMagasin),
   FOREIGN KEY(CodeUser) REFERENCES UTILISATEUR(CodeUser),
   FOREIGN KEY(CodeMagasin) REFERENCES MAGASIN(CodeMagasin)
);
