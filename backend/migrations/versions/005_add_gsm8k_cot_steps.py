"""add gsm8k cot steps

Revision ID: 005
Revises: 004
Create Date: 2024-03-21 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'gsm8k_cot_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gsm8k_cot_id', sa.Integer(), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('step_text', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['gsm8k_cot_id'], ['gsm8k_cot.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('gsm8k_cot_id', 'step_number', name='uix_cot_step_number')
    )
    
    # Add index for faster lookups
    op.create_index(
        'ix_gsm8k_cot_steps_cot_id',
        'gsm8k_cot_steps',
        ['gsm8k_cot_id']
    )


def downgrade() -> None:
    op.drop_index('ix_gsm8k_cot_steps_cot_id')
    op.drop_table('gsm8k_cot_steps') 