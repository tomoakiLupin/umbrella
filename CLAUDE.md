# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Discord高权限管理机器人 (Discord high-permission management bot) built with Python and discord.py. It provides administrative role management and dual-confirmation mechanisms for message deletion and channel creation operations.

## Development Commands

### Installation and Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot (will create config.ini on first run)
python main.py
```

### Configuration
- Edit `config.ini` after first run to set:
  - `bot.token`: Discord bot token from Discord Developer Portal
  - `admin.super_admin_id`: Discord user ID of the super administrator

### Running the Bot
```bash
python main.py
```

## Architecture

### Core Components

- **main.py**: Entry point and bot initialization with DiscordBot class

#### Core Systems (`src/core/`)
- **config.py**: Configuration parser that handles config.ini file creation and validation
- **logger.py**: Logging system with file and console output support
- **database.py**: SQLite database manager with migration functionality from JSON to SQLite

#### Managers (`src/managers/`)
- **admin_manager.py**: Admin role management system with JSON persistence
- **owner_channel_manager.py**: Owner channel system management with SQLite database persistence

#### Commands (`src/commands/`)
- **commands.py**: Discord slash commands implementation with confirmation workflows
- **owner_channel_commands.py**: Owner channel panel and archive commands with UI components

### Key Design Patterns

- **Modular Architecture**: Each component has a single responsibility (config, logging, admin management, commands)
- **Dual Confirmation System**: Administrative actions like message deletion and channel creation require confirmation from a second administrator
- **Role-Based Permissions**: Three-tier permission system (super admin, admin roles, regular users)
- **Persistent Storage**: Admin roles stored in `admin_data.json`, owner channel data in SQLite database (`owner_channel.db`), logs in `logs/` directory

### Permission System

1. **Super Admin**: Configured in config.ini, can add/remove admin roles
2. **Admin Roles**: Can execute deletion and channel creation commands
3. **Dual Confirmation**: Prevents single-admin abuse by requiring second admin confirmation

### Command Flow

Commands use Discord's UI Views with buttons for confirmation workflows:
- **Delete Post**: 10-second activation delay + confirmation from different admin
- **Create Channel**: Immediate confirmation available from different admin
- **Role Management**: Super admin only, immediate execution
- **Owner Channel Panel**: Interactive button for users to submit complaints/feedback
- **Owner Channel Archive**: 60-second countdown with cancellation option before auto-archive

### Project Structure

```
umbrella/
├── main.py                    # Bot entry point
├── config.ini                 # Bot configuration (created on first run)
├── requirements.txt           # Python dependencies
├── CLAUDE.md                 # Documentation for Claude Code
├── src/                      # Source code organized by responsibility
│   ├── core/                 # Core systems
│   │   ├── __init__.py
│   │   ├── config.py         # Configuration management
│   │   ├── logger.py         # Logging system
│   │   └── database.py       # SQLite database manager
│   ├── managers/             # Data managers
│   │   ├── __init__.py
│   │   ├── admin_manager.py  # Admin role management
│   │   └── owner_channel_manager.py  # Owner channel system
│   └── commands/             # Discord commands
│       ├── __init__.py
│       ├── commands.py       # Basic admin commands
│       └── owner_channel_commands.py  # Owner channel commands
├── logs/                     # Log files (auto-generated)
├── admin_data.json          # Admin roles (auto-generated)
└── owner_channel.db         # SQLite database (auto-generated)
```

### Data Storage

- **config.ini**: Bot configuration and super admin ID
- **admin_data.json**: Runtime-generated admin roles (automatically managed)
- **owner_channel.db**: SQLite database containing all owner channel system data
- **logs/**: Daily log files named `bot_YYYYMMDD.log`

## Available Commands

### Super Admin Commands
- `/创建服主通道面板`: Creates or updates owner channel panel with approval workflow, role restrictions, and time requirements
- `/添加管理员角色`: Add admin role
- `/移除管理员角色`: Remove admin role

### Admin Commands  
- `/查看管理员角色`: List admin roles
- `/删除帖子`: Delete posts with dual confirmation
- `/创建频道`: Create private channels with dual confirmation

### Super Admin & Owner Commands
- `/服主通道黑名单`: Unified blacklist management with operation type choices (add/remove/view) and optional user parameter
- `/服主通道归档`: Archive owner channels (60-second countdown) - Only super admin or designated owner can use

### User Interactive Features
- **Owner Channel Panel**: Click button to submit complaints/feedback, requires owner approval before channel creation

### Owner Approval System
- **Approval**: Creates private channel and notifies user via DM
- **Reject**: Sends custom rejection reason to user via DM
- **Ignore**: Silently dismisses the request
- **Blacklist**: Blocks user from future requests (shows fake API rate limit message)

## Database Migration

The owner channel system has been migrated from JSON files to SQLite database for better performance and reliability.

### Migration Process
- **Automatic Migration**: When OwnerChannelManager initializes, it automatically migrates data from JSON files to SQLite
- **Data Preserved**: All existing panel configurations, channels, blacklists, and pending requests are preserved
- **Backup Created**: Original JSON files are renamed with `.backup` extension
- **Database File**: `owner_channel.db` in the project root directory

### Database Schema
- **panel_configs**: Guild panel configurations with allowed roles and time restrictions
- **owner_channels**: Active and archived channel records
- **channel_counters**: Channel numbering counters per guild
- **blacklist**: User blacklist with tracking of who added them
- **pending_requests**: User requests awaiting owner approval
- **admin_roles**: Admin roles (migrated from admin_data.json)

## Important Implementation Notes

- The bot uses Chinese language for user-facing commands and messages
- All admin operations are logged with detailed information
- Bot requires message_content and members intents to function properly
- Error handling includes Discord permission and rate limit scenarios
- Configuration validation prevents startup with default/invalid tokens
- Owner channel system stores configuration dynamically via commands (not config file)
- HTML conversation archives are generated with full styling and message history
- Owner channel names follow pattern "服主通道-{number}" for easy identification
- Owner channels are only visible to: user who created it, designated owner, and super admin (not regular admin roles)
- Creating a new panel automatically replaces any existing panel configuration for that server
- User eligibility checked by: role requirements, server membership duration, blacklist status, and pending requests
- Blacklisted users see fake "API rate limit" message instead of actual blacklist notification
- Users with pending requests cannot submit new requests until current one is processed
- Approval workflow includes review channel where owner can approve/reject/ignore/blacklist requests
- Role restrictions: comma-separated @role mentions in panel creation command
- Time restrictions: minimum days since joining server (0 = no restriction)
- Manual blacklist management: super admins can add/remove users and view blacklist