"""add trie_evaled column

Revision ID: add_trie_evaled_column
Revises: 007
Create Date: 2024-03-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'add_trie_evaled_column'
down_revision: Union[str, None] = '007'  # Replace with actual previous revision
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add trie_evaled column as JSONB
    op.add_column('cot_tries', 
        sa.Column('trie_evaled', JSONB, 
            nullable=True  # Allow NULL for unevaluated tries
        )
    )
    
    # Add index for faster queries
    op.create_index(
        'ix_cot_tries_trie_evaled',
        'cot_tries',
        ['trie_evaled'],
        postgresql_using='gin'  # Use GIN index for JSON
    )


def downgrade() -> None:
    # Remove index first
    op.drop_index('ix_cot_tries_trie_evaled')
    
    # Then remove column
    op.drop_column('cot_tries', 'trie_evaled')