"""add cot trie table

Revision ID: 007
Revises: 006
Create Date: 2024-03-22 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cot_tries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dataset', sa.String(50), nullable=False, server_default='gsm8k'),
        sa.Column('problem_id', sa.Integer(), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('trie', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Add an index for faster lookups by dataset and problem_id
    op.create_index(
        'ix_cot_tries_dataset_problem_id',
        'cot_tries',
        ['dataset', 'problem_id']
    )

    # Add a unique constraint to prevent duplicate tries for the same problem/model combination
    op.create_unique_constraint(
        'uq_cot_tries_dataset_problem_model',
        'cot_tries',
        ['dataset', 'problem_id', 'model']
    )


def downgrade() -> None:
    op.drop_constraint('uq_cot_tries_dataset_problem_model', 'cot_tries')
    op.drop_index('ix_cot_tries_dataset_problem_id')
    op.drop_table('cot_tries') 