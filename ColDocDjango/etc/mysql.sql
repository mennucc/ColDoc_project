CREATE USER '@MYSQL_USERNAME@'@'localhost' IDENTIFIED BY '@MYSQL_PASSWORD@' ;

CREATE DATABASE @MYSQL_DATABASE@ CHARACTER SET utf8mb4 ;

GRANT ALL ON @MYSQL_DATABASE@.* TO '@MYSQL_USERNAME@'@'localhost' ; 

FLUSH PRIVILEGES;
