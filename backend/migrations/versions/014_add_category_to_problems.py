"""add category and metadata to problems

Revision ID: 014
Revises: 013
Create Date: 2024-01-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic
revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None

def upgrade():
    # Add category and problem_metadata columns to problems table
    op.add_column('problems',
        sa.Column('category', sa.String(100), nullable=True)
    )
    op.add_column('problems',
        sa.Column('problem_metadata', JSONB, nullable=True)
    )

def downgrade():
    # Remove problem_metadata and category columns from problems table
    op.drop_column('problems', 'problem_metadata')
    op.drop_column('problems', 'category') 