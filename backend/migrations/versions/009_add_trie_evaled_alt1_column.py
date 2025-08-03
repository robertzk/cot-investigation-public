"""add trie_evaled_alt1 column

Revision ID: add_trie_evaled_alt1_column
Revises: add_trie_evaled_column
Create Date: 2024-03-27 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'add_trie_evaled_alt1_column'
down_revision: Union[str, None] = 'add_trie_evaled_column'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add trie_evaled_alt1 column as JSONB
    op.add_column('cot_tries', 
        sa.Column('trie_evaled_alt1', JSONB, 
            nullable=True  # Allow NULL for unevaluated tries
        )
    )

    # Copy trie_evaled data to trie_evaled_alt1
    op.execute("""
        UPDATE cot_tries 
        SET trie_evaled_alt1 = trie_evaled
        WHERE trie_evaled IS NOT NULL
    """)
    
    # Add index for faster queries
    op.create_index(
        'ix_cot_tries_trie_evaled_alt1',
        'cot_tries',
        ['trie_evaled_alt1'],
        postgresql_using='gin'  # Use GIN index for JSON
    )


def downgrade() -> None:
    # Remove index first
    op.drop_index('ix_cot_tries_trie_evaled_alt1')
    
    # Then remove column
    op.drop_column('cot_tries', 'trie_evaled_alt1') 