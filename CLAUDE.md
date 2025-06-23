# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Django Management
- `python manage.py runserver` - Start development server
- `python manage.py makemigrations` - Create new migrations
- `python manage.py migrate` - Apply migrations to default database
- `python manage.py createsuperuser` - Create admin user
- `python manage.py shell` - Access Django shell

### Multi-tenant Database Management
- `python manage.py migrate_all_businesses` - Migrate all business databases
- `python manage.py create_business_db <business_id>` - Create database for specific business
- `python manage.py list_business_dbs` - List all business databases
- `python manage.py clean_business_dbs` - Clean unused business databases
- `python manage.py test_business_db <business_id>` - Test specific business database

### Package Management
- `poetry install` - Install dependencies
- `poetry add <package>` - Add new dependency
- `poetry shell` - Activate virtual environment

## Architecture Overview

This is a Django REST API application with a multi-tenant architecture for restaurant/business management. Each business operates with its own isolated database while sharing core authentication and business management functionality.

### Multi-Tenant Database Architecture
- **Core Database (`db_django_core.sqlite3`)**: Stores user accounts, business definitions, roles, and core system data
- **Business Databases (`db_business_X.sqlite3`)**: Each business has its own database for posts, inventory, and business-specific data
- **Database Router (`config/db_routers.py`)**: Routes queries to appropriate database based on business context
- **Business Middleware (`config/middleware.py`)**: Sets business context for each request using thread-local storage

### Core Apps Structure
- **accounts**: Custom user model with business associations and role-based permissions
- **business**: Business management, join requests, invitations, and branches
- **roles**: Business-specific role definitions and permissions
- **posts**: Content management (business-specific data)
- **inventory**: Inventory management (business-specific data)
- **settings**: Application configuration (business-specific data)
- **core**: Management commands and utilities

### Authentication & Authorization
- JWT-based authentication using `djangorestframework-simplejwt`
- Custom user model extends `AbstractUser` with business association
- Role-based permissions through `BusinessRole` model
- Business-specific permissions checked via `has_business_permission()` method

### Key Models
- `CustomUser`: Extended user model with business and role associations
- `Business`: Business entity with owner/co-owner relationships and automatic database creation
- `BusinessRole`: Role definitions with associated permissions
- `BusinessJoinRequest`: Handles user requests to join businesses
- `BusinessInvitation`: Token-based invitation system

### Business Database Creation
When a new `Business` is created, the system automatically:
1. Creates a dedicated SQLite database file (`db_business_X.sqlite3`)
2. Runs migrations for business-specific apps
3. Configures database routing for the new business

### API Structure
All API endpoints follow REST conventions:
- Authentication endpoints: `/api/auth/`
- Business management: `/api/business/`
- Role management: `/api/roles/`
- Posts: `/api/posts/`
- Inventory: `/api/inventory/`
- Settings: `/api/settings/`

### Database Context Management
The application uses thread-local storage to maintain business context:
- `BusinessMiddleware` extracts business ID from authenticated user
- `BusinessRouter` routes database queries based on current business context
- Business-specific data automatically goes to the correct database

### Important Conventions
- All business-specific models should be defined in their respective apps (posts, inventory, settings)
- Core models (users, businesses, roles) always use the default database
- Use `get_current_business_id()` to access current business context
- Business names are automatically converted to use underscores instead of spaces
- All user-facing text uses Django's internationalization with Spanish as default

### Development Notes
- The application supports both Spanish and English languages
- Logging is configured for both console and file output
- CORS is configured for local development
- Environment variables are loaded via python-dotenv
- Development uses SQLite, but PostgreSQL is recommended for production