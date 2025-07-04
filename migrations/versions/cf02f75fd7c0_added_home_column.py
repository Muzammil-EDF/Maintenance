"""ADDED HOME COLUMN

Revision ID: cf02f75fd7c0
Revises: feb057e869fe
Create Date: 2025-06-13 11:15:27.314909

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cf02f75fd7c0'
down_revision = 'feb057e869fe'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('todo', schema=None) as batch_op:
        batch_op.add_column(sa.Column('home', sa.String(length=500), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('todo', schema=None) as batch_op:
        batch_op.drop_column('home')

    # ### end Alembic commands ###
