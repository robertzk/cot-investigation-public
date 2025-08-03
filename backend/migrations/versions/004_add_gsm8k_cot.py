"""add gsm8k chain of thought responses

Revision ID: 004
Revises: 003
Create Date: 2024-03-21 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'gsm8k_cot',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gsm8k_id', sa.Integer(), nullable=False),
        sa.Column('language_model_id', sa.Integer(), nullable=False),
        sa.Column('params', sa.JSON(), nullable=False),
        sa.Column('raw_response', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['gsm8k_id'], ['gsm8k.id'], ),
        sa.ForeignKeyConstraint(['language_model_id'], ['language_models.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    # Add an index for faster lookups
    op.create_index(
        'ix_gsm8k_cot_gsm8k_id_language_model_id',
        'gsm8k_cot',
        ['gsm8k_id', 'language_model_id']
    )


def downgrade() -> None:
    op.drop_index('ix_gsm8k_cot_gsm8k_id_language_model_id')
    op.drop_table('gsm8k_cot') 