# This snippet may be used to setup the MySQL database for Django

# (Do not forget to pip install mysqlclient .)

# A SQL snippet is available in mysql.sql to setup the database.
# (It should be run with high priviledges.)

# Credentials are also stored in the mysql.cnf file, that you may copy to ~/.my.cnf

MYSQL_DATABASE = 'coldoc_db'
MYSQL_USERNAME = 'coldoc_user'
# (The password was randomized when deploying this coldoc site.)
MYSQL_PASSWORD = '@MYSQL_PASSWORD@'

DATABASES['default'] = {
    'ENGINE': 'django.db.backends.mysql',
    'NAME': MYSQL_DATABASE,
    'USER': MYSQL_USERNAME,
    'PASSWORD': MYSQL_PASSWORD,
}
