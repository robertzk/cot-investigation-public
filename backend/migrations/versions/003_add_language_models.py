"""add language models

Revision ID: 003
Revises: 002
Create Date: 2024-03-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the language_models table
    op.create_table(
        'language_models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('model_provider', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_name')
    )
    
    # Seed the initial Anthropic models
    op.execute("""
        INSERT INTO language_models (model_name, model_provider) VALUES
        ('claude-3-5-sonnet-20240620', 'Anthropic'),
        ('claude-3-opus-20240229', 'Anthropic'),
        ('claude-3-sonnet-20240229', 'Anthropic'),
        ('claude-3-haiku-20240307', 'Anthropic')
    """)


def downgrade() -> None:
    op.drop_table('language_models') 