"""add gsm8k cot step evaluations

Revision ID: 006
Revises: 005
Create Date: 2024-03-21 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the evaluations table
    op.create_table(
        'gsm8k_cot_step_evals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('step_id', sa.Integer(), nullable=False),
        sa.Column('correct', sa.String(10), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('explanation', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['step_id'], ['gsm8k_cot_steps.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add index for faster lookups
    op.create_index(
        'ix_gsm8k_cot_step_evals_step_id',
        'gsm8k_cot_step_evals',
        ['step_id']
    )


def downgrade() -> None:
    op.drop_index('ix_gsm8k_cot_step_evals_step_id')
    op.drop_table('gsm8k_cot_step_evals')
    op.execute('DROP TYPE step_correctness') 