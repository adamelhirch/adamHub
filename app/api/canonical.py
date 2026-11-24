from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from app.api._crud import apply_updates, create, delete, save
from app.api.deps import CurrentOrOwnerUser, SessionDep
from app.models import (
    DietaryPreference,
    Ingredient,
    Tag,
    UnitOfMeasure,
    UserDietaryPreference,
    Utensil,
)
from app.schemas.canonical import (
    DietaryPreferenceCreate,
    DietaryPreferenceRead,
    IngredientCreate,
    IngredientRead,
    IngredientUpdate,
    TagCreate,
    TagRead,
    UnitOfMeasureCreate,
    UnitOfMeasureRead,
    UserDietaryPreferencesSet,
    UtensilCreate,
    UtensilRead,
)

router = APIRouter(tags=["canonical"])


# ===========================================================================
# 1. Unités de Mesure (/units)
# ===========================================================================

@router.get("/units", response_model=list[UnitOfMeasureRead])
def list_units_of_measure(
    session: SessionDep,
    _user: CurrentOrOwnerUser,
) -> list[UnitOfMeasureRead]:
    units = session.exec(select(UnitOfMeasure).order_by(UnitOfMeasure.code.asc())).all()
    return [UnitOfMeasureRead.model_validate(u, from_attributes=True) for u in units]


@router.post("/units", response_model=UnitOfMeasureRead, status_code=status.HTTP_201_CREATED)
def create_unit_of_measure(
    payload: UnitOfMeasureCreate,
    session: SessionDep,
    _user: CurrentOrOwnerUser,
) -> UnitOfMeasureRead:
    existing = session.get(UnitOfMeasure, payload.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Unit of measure '{payload.code}' already exists",
        )
    unit = create(session, UnitOfMeasure(**payload.model_dump()))
    return UnitOfMeasureRead.model_validate(unit, from_attributes=True)


# ===========================================================================
# 2. Ingrédients Canoniques (/ingredients)
# ===========================================================================

@router.get("/ingredients", response_model=list[IngredientRead])
def list_ingredients(
    session: SessionDep,
    _user: CurrentOrOwnerUser,
    query: str | None = None,
    category: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[IngredientRead]:
    statement = select(Ingredient).order_by(Ingredient.name.asc())
    if query:
        statement = statement.where(Ingredient.name.ilike(f"%{query.strip()}%"))
    if category:
        statement = statement.where(Ingredient.category == category)
    statement = statement.offset(offset).limit(limit)

    ingredients = session.exec(statement).all()
    return [IngredientRead.model_validate(i, from_attributes=True) for i in ingredients]


@router.post("/ingredients", response_model=IngredientRead, status_code=status.HTTP_201_CREATED)
def create_ingredient(
    payload: IngredientCreate,
    session: SessionDep,
    _user: CurrentOrOwnerUser,
) -> IngredientRead:
    clean_name = payload.name.strip()
    existing = session.exec(select(Ingredient).where(Ingredient.name.ilike(clean_name))).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ingredient '{clean_name}' already exists",
        )

    if payload.default_unit_code:
        unit = session.get(UnitOfMeasure, payload.default_unit_code)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown unit code '{payload.default_unit_code}'",
            )

    data = payload.model_dump()
    data["name"] = clean_name
    ingredient = create(session, Ingredient(**data))
    return IngredientRead.model_validate(ingredient, from_attributes=True)


@router.get("/ingredients/{ingredient_id}", response_model=IngredientRead)
def get_ingredient(
    ingredient_id: int,
    session: SessionDep,
    _user: CurrentOrOwnerUser,
) -> IngredientRead:
    ingredient = session.get(Ingredient, ingredient_id)
    if not ingredient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found")
    return IngredientRead.model_validate(ingredient, from_attributes=True)


@router.patch("/ingredients/{ingredient_id}", response_model=IngredientRead)
def update_ingredient(
    ingredient_id: int,
    payload: IngredientUpdate,
    session: SessionDep,
    _user: CurrentOrOwnerUser,
) -> IngredientRead:
    ingredient = session.get(Ingredient, ingredient_id)
    if not ingredient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"]:
        clean_name = updates["name"].strip()
        existing = session.exec(
            select(Ingredient).where(Ingredient.name.ilike(clean_name), Ingredient.id != ingredient_id)
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ingredient with name '{clean_name}' already exists",
            )
        updates["name"] = clean_name

    if "default_unit_code" in updates and updates["default_unit_code"]:
        unit = session.get(UnitOfMeasure, updates["default_unit_code"])
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown unit code '{updates['default_unit_code']}'",
            )

    apply_updates(ingredient, updates, touch=True)
    ingredient = save(session, ingredient)
    return IngredientRead.model_validate(ingredient, from_attributes=True)


@router.delete("/ingredients/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ingredient(
    ingredient_id: int,
    session: SessionDep,
    _user: CurrentOrOwnerUser,
) -> None:
    ingredient = session.get(Ingredient, ingredient_id)
    if not ingredient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found")
    delete(session, ingredient)


# ===========================================================================
# 3. Ustensiles (/utensils)
# ===========================================================================

@router.get("/utensils", response_model=list[UtensilRead])
def list_utensils(
    session: SessionDep,
    _user: CurrentOrOwnerUser,
    query: str | None = None,
) -> list[UtensilRead]:
    statement = select(Utensil).order_by(Utensil.name.asc())
    if query:
        statement = statement.where(Utensil.name.ilike(f"%{query.strip()}%"))
    utensils = session.exec(statement).all()
    return [UtensilRead.model_validate(u, from_attributes=True) for u in utensils]


@router.post("/utensils", response_model=UtensilRead, status_code=status.HTTP_201_CREATED)
def create_utensil(
    payload: UtensilCreate,
    session: SessionDep,
    _user: CurrentOrOwnerUser,
) -> UtensilRead:
    clean_name = payload.name.strip()
    existing = session.exec(select(Utensil).where(Utensil.name.ilike(clean_name))).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Utensil '{clean_name}' already exists",
        )
    utensil = create(session, Utensil(name=clean_name))
    return UtensilRead.model_validate(utensil, from_attributes=True)


# ===========================================================================
# 4. Tags (/tags)
# ===========================================================================

@router.get("/tags", response_model=list[TagRead])
def list_tags(
    session: SessionDep,
    _user: CurrentOrOwnerUser,
    query: str | None = None,
) -> list[TagRead]:
    statement = select(Tag).order_by(Tag.label.asc())
    if query:
        statement = statement.where(Tag.label.ilike(f"%{query.strip()}%"))
    tags = session.exec(statement).all()
    return [TagRead.model_validate(t, from_attributes=True) for t in tags]


@router.post("/tags", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    session: SessionDep,
    _user: CurrentOrOwnerUser,
) -> TagRead:
    clean_label = payload.label.strip()
    existing = session.exec(select(Tag).where(Tag.label.ilike(clean_label))).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tag '{clean_label}' already exists",
        )
    tag = create(session, Tag(label=clean_label))
    return TagRead.model_validate(tag, from_attributes=True)


# ===========================================================================
# 5. Régimes Alimentaires (/dietary-preferences)
# ===========================================================================

@router.get("/dietary-preferences", response_model=list[DietaryPreferenceRead])
def list_dietary_preferences(
    session: SessionDep,
    _user: CurrentOrOwnerUser,
) -> list[DietaryPreferenceRead]:
    preferences = session.exec(
        select(DietaryPreference).order_by(DietaryPreference.name.asc())
    ).all()
    return [DietaryPreferenceRead.model_validate(p, from_attributes=True) for p in preferences]


@router.post(
    "/dietary-preferences",
    response_model=DietaryPreferenceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dietary_preference(
    payload: DietaryPreferenceCreate,
    session: SessionDep,
    _user: CurrentOrOwnerUser,
) -> DietaryPreferenceRead:
    clean_name = payload.name.strip()
    existing = session.exec(
        select(DietaryPreference).where(DietaryPreference.name.ilike(clean_name))
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dietary preference '{clean_name}' already exists",
        )
    data = payload.model_dump()
    data["name"] = clean_name
    preference = create(session, DietaryPreference(**data))
    return DietaryPreferenceRead.model_validate(preference, from_attributes=True)


@router.get("/dietary-preferences/my", response_model=list[DietaryPreferenceRead])
def get_my_dietary_preferences(
    session: SessionDep,
    user: CurrentOrOwnerUser,
) -> list[DietaryPreferenceRead]:
    statement = (
        select(DietaryPreference)
        .join(UserDietaryPreference, UserDietaryPreference.dietary_preference_id == DietaryPreference.id)
        .where(UserDietaryPreference.user_id == user.id)
        .order_by(DietaryPreference.name.asc())
    )
    prefs = session.exec(statement).all()
    return [DietaryPreferenceRead.model_validate(p, from_attributes=True) for p in prefs]


@router.put("/dietary-preferences/my", response_model=list[DietaryPreferenceRead])
def set_my_dietary_preferences(
    payload: UserDietaryPreferencesSet,
    session: SessionDep,
    user: CurrentOrOwnerUser,
) -> list[DietaryPreferenceRead]:
    # 1. Vérifier que tous les IDs existent
    requested_ids = set(payload.dietary_preference_ids)
    if requested_ids:
        found_prefs = session.exec(
            select(DietaryPreference).where(DietaryPreference.id.in_(requested_ids))
        ).all()
        if len(found_prefs) != len(requested_ids):
            found_ids = {p.id for p in found_prefs}
            missing = requested_ids - found_ids
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown dietary preference IDs: {missing}",
            )
    else:
        found_prefs = []

    # 2. Supprimer les associations actuelles
    existing_links = session.exec(
        select(UserDietaryPreference).where(UserDietaryPreference.user_id == user.id)
    ).all()
    for link in existing_links:
        session.delete(link)

    # 3. Créer les nouvelles associations
    for pref_id in requested_ids:
        new_link = UserDietaryPreference(user_id=user.id, dietary_preference_id=pref_id)
        session.add(new_link)

    session.commit()

    # 4. Retourner la liste triée
    statement = (
        select(DietaryPreference)
        .join(UserDietaryPreference, UserDietaryPreference.dietary_preference_id == DietaryPreference.id)
        .where(UserDietaryPreference.user_id == user.id)
        .order_by(DietaryPreference.name.asc())
    )
    saved = session.exec(statement).all()
    return [DietaryPreferenceRead.model_validate(p, from_attributes=True) for p in saved]
