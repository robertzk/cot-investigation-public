"""create problems table

Revision ID: 013
Revises: 012_add_cot_path_table
Create Date: 2024-01-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic
revision = '013'
down_revision = '012_add_cot_path_table'
branch_labels = None
depends_on = None

def upgrade():
    # Create new problems table
    op.create_table(
        'problems',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dataset_name', sa.String(50), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_problems_dataset_name', 'problems', ['dataset_name'])

    # Migrate existing GSM8K data to problems table if it exists
    op.execute("""
        INSERT INTO problems (id, dataset_name, question, answer)
        SELECT id, 'gsm8k', question, answer FROM gsm8k
        ON CONFLICT (id) DO NOTHING
    """)

    # Update foreign key references in cot_tries
    # First check if the old constraint exists
    conn = op.get_bind()
    result = conn.execute(text("""
        SELECT constraint_name 
        FROM information_schema.table_constraints 
        WHERE table_name = 'cot_tries' 
        AND constraint_name = 'cot_tries_problem_id_fkey'
    """))
    if result.scalar():
        # Drop the old constraint only if it exists
        op.drop_constraint('cot_tries_problem_id_fkey', 'cot_tries', type_='foreignkey')
    
    # Create the new foreign key constraint
    op.create_foreign_key(
        'cot_tries_problem_id_fkey', 'cot_tries',
        'problems', ['problem_id'], ['id']
    )

    # Update foreign key references in experiment records
    # First check if the old constraint exists
    result = conn.execute(text("""
        SELECT constraint_name 
        FROM information_schema.table_constraints 
        WHERE table_name = 'cot_trie_eval_experiment_record' 
        AND constraint_name = 'cot_trie_eval_experiment_record_problem_id_fkey'
    """))
    if result.scalar():
        # Drop the old constraint only if it exists
        op.drop_constraint('cot_trie_eval_experiment_record_problem_id_fkey', 'cot_trie_eval_experiment_record', type_='foreignkey')
    
    # Create the new foreign key constraint
    op.create_foreign_key(
        'cot_trie_eval_experiment_record_problem_id_fkey', 'cot_trie_eval_experiment_record',
        'problems', ['problem_id'], ['id']
    )

def downgrade():
    # First check if the constraints exist and drop them if they do
    conn = op.get_bind()
    
    # Check and drop experiment record constraint
    result = conn.execute(text("""
        SELECT constraint_name 
        FROM information_schema.table_constraints 
        WHERE table_name = 'cot_trie_eval_experiment_record' 
        AND constraint_name = 'cot_trie_eval_experiment_record_problem_id_fkey'
    """))
    if result.scalar():
        op.drop_constraint('cot_trie_eval_experiment_record_problem_id_fkey', 'cot_trie_eval_experiment_record', type_='foreignkey')
    
    # Check and drop cot_tries constraint
    result = conn.execute(text("""
        SELECT constraint_name 
        FROM information_schema.table_constraints 
        WHERE table_name = 'cot_tries' 
        AND constraint_name = 'cot_tries_problem_id_fkey'
    """))
    if result.scalar():
        op.drop_constraint('cot_tries_problem_id_fkey', 'cot_tries', type_='foreignkey')

    # Create the old foreign key constraints if gsm8k table exists
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'gsm8k'
        )
    """))
    if result.scalar():
        op.create_foreign_key(
            'cot_trie_eval_experiment_record_problem_id_fkey', 'cot_trie_eval_experiment_record',
            'gsm8k', ['problem_id'], ['id']
        )
        op.create_foreign_key(
            'cot_tries_problem_id_fkey', 'cot_tries',
            'gsm8k', ['problem_id'], ['id']
        )

    # Drop problems table
    op.drop_index('ix_problems_dataset_name', 'problems')
    op.drop_table('problems') 