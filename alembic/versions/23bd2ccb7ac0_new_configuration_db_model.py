"""New Configuration DB Model

Revision ID: 23bd2ccb7ac0
Revises: 
Create Date: 2017-03-07 15:51:21.392832

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '23bd2ccb7ac0'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('MasterConfigurations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('Links',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('data', sa.Text(), nullable=True),
    sa.Column('master_conf_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['master_conf_id'], ['MasterConfigurations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('Configurations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('data', sa.Text(), nullable=True),
    sa.Column('package', sa.Text(), nullable=True),
    sa.Column('master_conf_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['master_conf_id'], ['MasterConfigurations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('from_conf_to_link_table',
    sa.Column('conf_id', sa.Integer(), nullable=True),
    sa.Column('link_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['conf_id'], ['Configurations.id'], ),
    sa.ForeignKeyConstraint(['link_id'], ['Links.id'], )
    )
    op.create_table('from_link_to_conf_table',
    sa.Column('link_id', sa.Integer(), nullable=True),
    sa.Column('conf_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['conf_id'], ['Configurations.id'], ),
    sa.ForeignKeyConstraint(['link_id'], ['Links.id'], )
    )
    op.drop_table('icingaConfig')
    op.add_column('openwrt', sa.Column('master_conf_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'openwrt', 'MasterConfigurations', ['master_conf_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'openwrt', type_='foreignkey')
    op.drop_column('openwrt', 'master_conf_id')
    op.create_table('icingaConfig',
    sa.Column('url', sa.TEXT(), nullable=False),
    sa.Column('login', sa.TEXT(), nullable=True),
    sa.Column('password', sa.TEXT(), nullable=True),
    sa.Column('port', sa.INTEGER(), nullable=True),
    sa.Column('verify', sa.BOOLEAN(), nullable=True),
    sa.PrimaryKeyConstraint('url')
    )
    op.drop_table('from_link_to_conf_table')
    op.drop_table('from_conf_to_link_table')
    op.drop_table('Configurations')
    op.drop_table('Links')
    op.drop_table('MasterConfigurations')
    # ### end Alembic commands ###