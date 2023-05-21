CREATE USER 'coldoc_user'@'localhost' IDENTIFIED BY '@MYSQL_PASSWORD@' ;

CREATE DATABASE coldoc_db CHARACTER SET utf8 ;

GRANT ALL ON coldoc_db.* TO 'coldoc_user'@'localhost' ; 

FLUSH PRIVILEGES;
