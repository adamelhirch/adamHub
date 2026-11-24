"""add_merise_canonical_models

Revision ID: f8c959b4622c
Revises: da1365f53d1a
Create Date: 2026-09-28 16:29:53.326841

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'f8c959b4622c'
down_revision: Union[str, Sequence[str], None] = 'da1365f53d1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - additive migration for canonical Merise models."""
    # 1. Tables de référence indépendantes
    op.create_table(
        'dietarypreference',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dietarypreference_name'), 'dietarypreference', ['name'], unique=True)

    op.create_table(
        'tag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('label', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tag_label'), 'tag', ['label'], unique=True)

    op.create_table(
        'unitofmeasure',
        sa.Column('code', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column('label', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('magnitude_type', sqlmodel.sql.sqltypes.AutoString(length=30), nullable=False),
        sa.Column('conversion_factor_to_base', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('code')
    )

    op.create_table(
        'utensil',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_utensil_name'), 'utensil', ['name'], unique=True)

    # 2. Ingrédients canoniques (dépend de unitofmeasure)
    op.create_table(
        'ingredient',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=150), nullable=False),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column('default_unit_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['default_unit_code'], ['unitofmeasure.code'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ingredient_category'), 'ingredient', ['category'], unique=False)
    op.create_index(op.f('ix_ingredient_name'), 'ingredient', ['name'], unique=True)

    # 3. Associations Utilisateur & Préférences
    op.create_table(
        'userdietarypreference',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('dietary_preference_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dietary_preference_id'], ['dietarypreference.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'dietary_preference_id', name='uq_user_dietary_preference')
    )
    op.create_index(op.f('ix_userdietarypreference_dietary_preference_id'), 'userdietarypreference', ['dietary_preference_id'], unique=False)
    op.create_index(op.f('ix_userdietarypreference_user_id'), 'userdietarypreference', ['user_id'], unique=False)

    # 4. Détails des recettes (Étapes, Ustensiles, Tags)
    op.create_table(
        'recipestep',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('instruction', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recipestep_recipe_id'), 'recipestep', ['recipe_id'], unique=False)

    op.create_table(
        'recipetag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tag.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recipe_id', 'tag_id', name='uq_recipe_tag')
    )
    op.create_index(op.f('ix_recipetag_recipe_id'), 'recipetag', ['recipe_id'], unique=False)
    op.create_index(op.f('ix_recipetag_tag_id'), 'recipetag', ['tag_id'], unique=False)

    op.create_table(
        'recipeutensil',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('utensil_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['utensil_id'], ['utensil.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recipe_id', 'utensil_id', name='uq_recipe_utensil')
    )
    op.create_index(op.f('ix_recipeutensil_recipe_id'), 'recipeutensil', ['recipe_id'], unique=False)
    op.create_index(op.f('ix_recipeutensil_utensil_id'), 'recipeutensil', ['utensil_id'], unique=False)

    # 5. Liaisons vers Ingredient canonique sur les tables existantes
    op.add_column('groceryitem', sa.Column('ingredient_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_groceryitem_ingredient_id'), 'groceryitem', ['ingredient_id'], unique=False)
    op.create_foreign_key('fk_groceryitem_ingredient_id', 'groceryitem', 'ingredient', ['ingredient_id'], ['id'], ondelete='SET NULL')

    op.add_column('pantryitem', sa.Column('ingredient_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_pantryitem_ingredient_id'), 'pantryitem', ['ingredient_id'], unique=False)
    op.create_foreign_key('fk_pantryitem_ingredient_id', 'pantryitem', 'ingredient', ['ingredient_id'], ['id'], ondelete='SET NULL')

    op.add_column('recipeingredient', sa.Column('ingredient_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_recipeingredient_ingredient_id'), 'recipeingredient', ['ingredient_id'], unique=False)
    op.create_foreign_key('fk_recipeingredient_ingredient_id', 'recipeingredient', 'ingredient', ['ingredient_id'], ['id'], ondelete='SET NULL')

    op.add_column('supermarketproduct', sa.Column('ingredient_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_supermarketproduct_ingredient_id'), 'supermarketproduct', ['ingredient_id'], unique=False)
    op.create_foreign_key('fk_supermarketproduct_ingredient_id', 'supermarketproduct', 'ingredient', ['ingredient_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema - roll back canonical Merise models."""
    op.drop_constraint('fk_supermarketproduct_ingredient_id', 'supermarketproduct', type_='foreignkey')
    op.drop_index(op.f('ix_supermarketproduct_ingredient_id'), table_name='supermarketproduct')
    op.drop_column('supermarketproduct', 'ingredient_id')

    op.drop_constraint('fk_recipeingredient_ingredient_id', 'recipeingredient', type_='foreignkey')
    op.drop_index(op.f('ix_recipeingredient_ingredient_id'), table_name='recipeingredient')
    op.drop_column('recipeingredient', 'ingredient_id')

    op.drop_constraint('fk_pantryitem_ingredient_id', 'pantryitem', type_='foreignkey')
    op.drop_index(op.f('ix_pantryitem_ingredient_id'), table_name='pantryitem')
    op.drop_column('pantryitem', 'ingredient_id')

    op.drop_constraint('fk_groceryitem_ingredient_id', 'groceryitem', type_='foreignkey')
    op.drop_index(op.f('ix_groceryitem_ingredient_id'), table_name='groceryitem')
    op.drop_column('groceryitem', 'ingredient_id')

    op.drop_table('recipeutensil')
    op.drop_table('recipetag')
    op.drop_table('recipestep')
    op.drop_table('userdietarypreference')
    op.drop_table('ingredient')
    op.drop_table('utensil')
    op.drop_table('unitofmeasure')
    op.drop_table('tag')
    op.drop_table('dietarypreference')
