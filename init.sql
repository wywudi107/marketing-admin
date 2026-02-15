-- 营销后台管理系统 - 数据库初始化脚本

CREATE DATABASE IF NOT EXISTS `marketing_admin` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `marketing_admin`;

-- 管理员角色表
CREATE TABLE IF NOT EXISTS `admin_roles` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '角色ID',
  `role_name` VARCHAR(50) NOT NULL COMMENT '角色名称',
  `role_key` VARCHAR(50) NOT NULL COMMENT '角色标识',
  `permissions` JSON NOT NULL COMMENT '权限列表（JSON数组）',
  `status` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '0=禁用,1=启用',
  `remark` VARCHAR(255) DEFAULT NULL COMMENT '备注',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_role_key` (`role_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管理员角色表';

-- 管理员用户表
CREATE TABLE IF NOT EXISTS `admin_users` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '管理员ID',
  `username` VARCHAR(50) NOT NULL COMMENT '登录账号',
  `password` VARCHAR(255) NOT NULL COMMENT '密码哈希（bcrypt）',
  `nickname` VARCHAR(50) DEFAULT NULL COMMENT '显示昵称',
  `role_id` INT UNSIGNED NOT NULL COMMENT '角色ID',
  `status` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '0=禁用,1=启用',
  `last_login_at` TIMESTAMP NULL DEFAULT NULL COMMENT '最后登录时间',
  `last_login_ip` VARCHAR(45) DEFAULT NULL COMMENT '最后登录IP',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`),
  KEY `idx_role_id` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管理员用户表';

-- 管理员操作日志表
CREATE TABLE IF NOT EXISTS `admin_operation_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `admin_id` INT UNSIGNED NOT NULL COMMENT '操作管理员ID',
  `admin_username` VARCHAR(50) NOT NULL COMMENT '管理员账号',
  `module` VARCHAR(50) NOT NULL COMMENT '操作模块',
  `action` VARCHAR(100) NOT NULL COMMENT '操作动作',
  `target_id` VARCHAR(50) DEFAULT NULL COMMENT '操作对象ID',
  `detail` TEXT DEFAULT NULL COMMENT '操作详情（JSON）',
  `ip` VARCHAR(45) DEFAULT NULL COMMENT '操作IP',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_admin_id` (`admin_id`),
  KEY `idx_module_created` (`module`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管理员操作日志表';

-- 初始数据：超级管理员角色
INSERT INTO `admin_roles` (`role_name`, `role_key`, `permissions`, `status`, `remark`) VALUES
('超级管理员', 'super_admin', '["admin_user:view","admin_user:create","admin_user:edit","admin_user:delete","admin_role:view","admin_role:create","admin_role:edit","admin_role:delete","operation_log:view"]', 1, '拥有所有权限');

-- 初始数据：默认管理员账号（密码: admin123）
INSERT INTO `admin_users` (`username`, `password`, `nickname`, `role_id`, `status`) VALUES
('admin', '$2b$12$dUnUkTVGjjIel9zItPid9OLEV32OY1zprlFuU326.yHxlO3RgZCzS', '超级管理员', 1, 1);
