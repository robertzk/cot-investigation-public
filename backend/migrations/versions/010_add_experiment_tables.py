"""add experiment tables

Revision ID: 010_add_experiment_tables
Revises: 009_add_trie_evaled_alt1_column
Create Date: 2024-03-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers
revision = '010_add_experiment_tables'
down_revision = 'add_trie_evaled_alt1_column'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create experiment table
    op.create_table(
        'cot_trie_eval_experiment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('experiment_desc', sa.String(), nullable=False),
        sa.Column('results', JSON, nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create experiment record table
    op.create_table(
        'cot_trie_eval_experiment_record',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('experiment_id', sa.Integer(), nullable=False),
        sa.Column('problem_id', sa.Integer(), nullable=False),
        sa.Column('cot_trie_id', sa.Integer(), nullable=False),
        sa.Column('trie_evaled', JSON, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['experiment_id'], ['cot_trie_eval_experiment.id']),
        sa.ForeignKeyConstraint(['problem_id'], ['gsm8k.id']),
        sa.ForeignKeyConstraint(['cot_trie_id'], ['cot_tries.id'])
    )

def downgrade() -> None:
    op.drop_table('cot_trie_eval_experiment_record')
    op.drop_table('cot_trie_eval_experiment') 