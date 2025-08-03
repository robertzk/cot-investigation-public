"""add cot path table

Revision ID: 012_add_cot_path_table
Revises: 011_add_model_to_experiment
Create Date: 2024-03-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '012_add_cot_path_table'
down_revision = '011_add_model_to_experiment'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create cot_path table
    op.create_table(
        'cot_path',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cot_trie_id', sa.Integer(), nullable=True),
        sa.Column('cot_trie_eval_experiment_record_id', sa.Integer(), nullable=True),
        sa.Column('node_ids', sa.JSON, nullable=False),
        sa.Column('cot_path', sa.JSON, nullable=False),
        sa.Column('answer_correct', sa.Boolean(), nullable=True),
        sa.Column('is_unfaithful', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['cot_trie_id'], ['cot_tries.id']),
        sa.ForeignKeyConstraint(
            ['cot_trie_eval_experiment_record_id'], 
            ['cot_trie_eval_experiment_record.id']
        ),
        # Ensure only one of cot_trie_id or experiment_record_id is present
        sa.CheckConstraint(
            '(cot_trie_id IS NULL AND cot_trie_eval_experiment_record_id IS NOT NULL) OR '
            '(cot_trie_id IS NOT NULL AND cot_trie_eval_experiment_record_id IS NULL)',
            name='exactly_one_reference_check'
        )
    )

    # Add indexes for performance
    op.create_index(
        'ix_cot_path_cot_trie_id',
        'cot_path',
        ['cot_trie_id']
    )
    op.create_index(
        'ix_cot_path_experiment_record_id',
        'cot_path',
        ['cot_trie_eval_experiment_record_id']
    )

def downgrade() -> None:
    op.drop_index('ix_cot_path_experiment_record_id')
    op.drop_index('ix_cot_path_cot_trie_id')
    op.drop_table('cot_path') 