"""add model to experiment record

Revision ID: 011_add_model_to_experiment
Revises: 010_add_experiment_tables
Create Date: 2024-03-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '011_add_model_to_experiment'
down_revision = '010_add_experiment_tables'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        'cot_trie_eval_experiment_record',
        sa.Column('model', sa.String(), nullable=True)
    )

def downgrade() -> None:
    op.drop_column('cot_trie_eval_experiment_record', 'model') 