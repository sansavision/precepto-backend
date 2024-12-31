import asyncio
import os
import bcrypt

import edgedb
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import print as rprint

import os
import sys
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from common.edgedb_client import EdgedbClient
from common.queries.user import user_create_async_edgeql, user_delete_async_edgeql, user_read_async_edgeql, user_update_async_edgeql, user_read_all_async_edgeql

# only in dev
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.pardir,".env"))

class Admin:
    def __init__(self):
        self.edge = EdgedbClient()
        self.client = self.edge.client
        self.console = Console()
        
    async def create_user(self):
        """Create a new user with CLI prompts"""
        try:
            self.console.print("\n[bold blue]Create New User[/bold blue]")
            
            username = Prompt.ask("[cyan]Enter username[/cyan]")
            password = Prompt.ask("[cyan]Enter password[/cyan]", password=True)
            
            # User type selection
            user_type = Prompt.ask(
                "[cyan]Select user type[/cyan]",
                choices=["admin", "regular"],
                default="regular"
            )
            
            # User category selection
            category = Prompt.ask(
                "[cyan]Select user category[/cyan]",
                choices=["physician", "others"],
                default="others"
            )
            
            # Hash password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

            await user_create_async_edgeql.user_create(self.client,user_name=username,login_pass=hashed_password.decode('utf-8'),is_admin=user_type == "admin",category=category) 
            self.console.print(f"\n[bold green]✓ User '{username}' created successfully![/bold green]")
        
        except edgedb.errors.ConstraintViolationError:
            self.console.print(f"\n[bold red]✗ Error: Username '{username}' already exists![/bold red]") 
        except Exception as e:
            self.console.print(f"\n[bold red]✗ Error creating user: {str(e)}[/bold red]")

    async def list_users(self):
        """List all users in a formatted table"""
        try:
            self.console.print("\n[bold blue]User List[/bold blue]")
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Username")
            table.add_column("Id")
            table.add_column("Type")
            table.add_column("Category")
            table.add_column("Last Login")
            table.add_column("Created At")
            users = await user_read_all_async_edgeql.user_read_all(self.client)
            for user in users:
                self.console.print("got user",user)
                user_json_dict = self.edge.serialize_edgedb_to_json_dict(user)
                self.console.print("got user json dict",user_json_dict)
                user_json_dict = self.edge.serialized_edgedb_json_dict_to_json(user)
                self.console.print("got user json str",user_json_dict)
                # user_from_json = user.from_json(user_json)
                user_type = "Admin" if user.is_admin else "Regular"
                last_login = user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else 'Never'
                created_at = user.created_at.strftime('%Y-%m-%d %H:%M:%S')
                
                table.add_row(
                    user.user_name,
                    str(user.id),
                    user_type,
                    user.category,
                    last_login,
                    created_at
                )
            
            self.console.print(table)
            
        except Exception as e:
            self.console.print(f"\n[bold red]✗ Error listing users: {str(e)}[/bold red]")

    async def delete_user(self):
        """Delete a user with confirmation"""
        try:
            self.console.print("\n[bold blue]Delete User[/bold blue]")
            
            user_id = Prompt.ask("[cyan]Enter id to delete[/cyan]")
            
            # user = await self.users_collection.find_one({"name": username})
            user = await user_read_async_edgeql.user_read(self.client,id=user_id)
            if not user:
                self.console.print(f"\n[bold red]✗ User with id '{user_id}' not found![/bold red]")
                return
            username = user.user_name    
            if user.is_admin:
                confirm = Confirm.ask(
                    f"[yellow]Warning: '{username}' is an admin user. Are you sure you want to delete?[/yellow]"
                )
            else:
                confirm = Confirm.ask(f"[yellow]Are you sure you want to delete user '{username}'?[/yellow]")
                
            if confirm:
                # result = await self.users_collection.delete_one({"name": username})
                await user_delete_async_edgeql.user_delete(self.client,id=user_id)
                self.console.print(f"\n[bold green]✓ User '{username}' deleted successfully![/bold green]")
            else:
                self.console.print("\n[yellow]Deletion cancelled.[/yellow]")
                
        except Exception as e:
            self.console.print(f"\n[bold red]✗ Error deleting user: {str(e)}[/bold red]")

    async def reset_password(self):
        """Reset a user's password"""
        try:
            self.console.print("\n[bold blue]Reset User Password[/bold blue]")
            
            user_id = Prompt.ask("[cyan]Enter user id[/cyan]")
            
            user = await user_read_async_edgeql.user_read(self.client,id=user_id)
            if not user:
                self.console.print(f"\n[bold red]✗ User id '{user_id}' not found![/bold red]")
                return
            username = user.user_name    
            new_password = Prompt.ask("[cyan]Enter new password[/cyan]", password=True)
            confirm_password = Prompt.ask("[cyan]Confirm new password[/cyan]", password=True)
            
            if new_password != confirm_password:
                self.console.print("\n[bold red]✗ Passwords do not match![/bold red]")
                return
                
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            
            await user_update_async_edgeql.user_update(self.client,id=user_id,login_pass=hashed_password.decode('utf-8'))
    
            self.console.print(f"\n[bold green]✓ Password reset successfully for user '{username}'![/bold green]")
                
        except Exception as e:
            self.console.print(f"\n[bold red]✗ Error resetting password: {str(e)}[/bold red]")

    async def modify_user_type(self):
        """Modify user type (admin/regular)"""
        try:
            self.console.print("\n[bold blue]Modify User Type[/bold blue]")
            
            user_id = Prompt.ask("[cyan]Enter user id[/cyan]")
            
            user = await user_read_async_edgeql.user_read(self.client,id=user_id)
            if not user:
                self.console.print(f"\n[bold red]✗ User with id '{user_id}' not found![/bold red]")
                return
            
            username = user.user_name    
            current_type = "admin" if user.is_admin else "regular"
            new_type = Prompt.ask(
                "[cyan]Select new user type[/cyan]",
                choices=["admin", "regular"],
                default=current_type
            )
            
            if new_type == current_type:
                self.console.print(f"\n[yellow]User '{username}' is already {new_type} type.[/yellow]")
                return

            await user_update_async_edgeql.user_update(self.client,id=user_id,is_admin=new_type == "admin", category=user.category)
            
            self.console.print(f"\n[bold green]✓ User '{username}' type changed to {new_type}![/bold green]")
                
        except Exception as e:
            self.console.print(f"\n[bold red]✗ Error modifying user type: {str(e)}[/bold red]")

    async def modify_user_category(self):
        """Modify user category"""
        try:
            self.console.print("\n[bold blue]Modify User Category[/bold blue]")
            
            user_id = Prompt.ask("[cyan]Enter user id[/cyan]")
            
            user = await user_read_async_edgeql.user_read(self.client,id=user_id)
            if not user:
                self.console.print(f"\n[bold red]✗ User id '{user_id}' not found![/bold red]")
                return
            username = user.user_name
            current_category = user.category
            new_category = Prompt.ask(
                "[cyan]Select new category[/cyan]",
                choices=["physician", "others"],
                default=current_category
            )
            
            if new_category == current_category:
                self.console.print(f"\n[yellow]User '{username}' is already in {new_category} category.[/yellow]")
                return

            await user_update_async_edgeql.user_update(self.client,id=user_id,category=new_category)
        
            self.console.print(f"\n[bold green]✓ User '{username}' category changed to {new_category}![/bold green]")
                
        except Exception as e:
            self.console.print(f"\n[bold red]✗ Error modifying user category: {str(e)}[/bold red]")

    async def run_cli(self):
        """Run the admin CLI interface"""
        while True:
            self.console.print("\n[bold blue]Admin Management CLI[/bold blue]")
            self.console.print("\n[cyan]Available commands:[/cyan]")
            self.console.print("1. Create user")
            self.console.print("2. List users")
            self.console.print("3. Delete user")
            self.console.print("4. Reset user password")
            self.console.print("5. Modify user type")
            self.console.print("6. Modify user category")
            self.console.print("7. Exit")
            
            choice = Prompt.ask("\n[cyan]Enter your choice[/cyan]", choices=["1", "2", "3", "4", "5", "6", "7"])
            
            if choice == "1":
                await self.create_user()
            elif choice == "2":
                await self.list_users()
            elif choice == "3":
                await self.delete_user()
            elif choice == "4":
                await self.reset_password()
            elif choice == "5":
                await self.modify_user_type()
            elif choice == "6":
                await self.modify_user_category()
            elif choice == "7":
                self.console.print("\n[bold green]Goodbye![/bold green]")
                break


if __name__ == "__main__":
    # Initialize the admin class
    admin = Admin()
    
    # Run the CLI
    asyncio.run(admin.run_cli())