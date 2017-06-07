"""Add revision model, add sync_diff to OpenWrt

Revision ID: 8c611fcc5826
Revises: a59b23b319f1
Create Date: 2017-05-24 13:24:39.575153

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c611fcc5826'
down_revision = 'a59b23b319f1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('Revisions',
    sa.Column('id', sa.Text(), nullable=False),
    sa.Column('previous', sa.Text(), nullable=True),
    sa.Column('next', sa.Text(), nullable=True),
    sa.Column('data', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )

    op.add_column('openwrt', sa.Column('synd_diff_rev_id', sa.Text(), nullable=True))
    op.create_foreign_key(None, 'openwrt', 'Revisions', ['synd_diff_rev_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    #op.drop_constraint(None, 'openwrt', type_='foreignkey')
    #op.drop_column('openwrt', 'synd_diff_rev_id')

    op.drop_table('Revisions')
    # ### end Alembic commands ###