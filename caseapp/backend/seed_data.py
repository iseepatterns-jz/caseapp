import asyncio
import uuid
import sys
import os
from datetime import datetime, timedelta, UTC

# Add current directory to path
sys.path.append(os.getcwd())

from core.database import engine, AsyncSessionLocal
from models.user import User, UserRole
from models.case import Case, CaseStatus, CaseType, CasePriority
from models.client import Client
from models.timeline import CaseTimeline, TimelineEvent, EventType
from core.auth import AuthService

async def seed():
    async with AsyncSessionLocal() as session:
        try:
            # 1. Create Users
            print("Creating users...")
            admin_pwd = AuthService.get_password_hash("Admin123!@#")
            attorney_pwd = AuthService.get_password_hash("Attorney123!@#")
            
            admin_user = User(
                username="admin",
                email="admin@iseepatterns.com",
                hashed_password=admin_pwd,
                first_name="Admin",
                last_name="User",
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True
            )
            
            attorney1 = User(
                username="jdoe",
                email="john.doe@iseepatterns.com",
                hashed_password=attorney_pwd,
                first_name="John",
                last_name="Doe",
                role=UserRole.ATTORNEY,
                is_active=True,
                is_verified=True
            )
            
            attorney2 = User(
                username="jsmith",
                email="jane.smith@iseepatterns.com",
                hashed_password=attorney_pwd,
                first_name="Jane",
                last_name="Smith",
                role=UserRole.ATTORNEY,
                is_active=True,
                is_verified=True
            )
            
            session.add_all([admin_user, attorney1, attorney2])
            await session.flush()
            
            # 2. Create Clients
            print("Creating clients...")
            client1 = Client(
                first_name="Robert",
                last_name="Johnson",
                email="robert.j@example.com",
                phone="555-0101",
                address_line1="123 Maple St",
                city="Boston",
                state="MA",
                zip_code="02108"
            )
            
            client2 = Client(
                first_name="Sarah",
                last_name="Williams",
                email="sarah.w@example.com",
                phone="555-0102",
                address_line1="456 Oak Ln",
                city="New York",
                state="NY",
                zip_code="10001"
            )
            
            client3 = Client(
                first_name="Michael",
                last_name="Chen",
                email="m.chen@example.com",
                phone="555-0103",
                company_name="Chen & Associates"
            )
            
            session.add_all([client1, client2, client3])
            await session.flush()
            
            # 3. Create Cases
            print("Creating cases...")
            cases_data = [
                {
                    "case_number": "CIV-2024-0001",
                    "title": "Johnson v. TechCorp",
                    "description": "Wrongful termination and breach of contract claim.",
                    "case_type": CaseType.CIVIL,
                    "status": CaseStatus.ACTIVE,
                    "priority": CasePriority.HIGH,
                    "client_id": client1.id,
                    "created_by": attorney1.id,
                    "court_name": "Massachussetts Superior Court",
                    "judge_name": "Hon. Elizabeth Warren"
                },
                {
                    "case_number": "CRM-2024-0042",
                    "title": "State v. Thompson",
                    "description": "Alleged financial fraud and money laundering.",
                    "case_type": CaseType.CRIMINAL,
                    "status": CaseStatus.PENDING,
                    "priority": CasePriority.URGENT,
                    "client_id": client3.id,
                    "created_by": attorney2.id,
                    "court_name": "SDNY District Court",
                    "judge_name": "Hon. Jed Rakoff"
                }
            ]
            
            for c_data in cases_data:
                case = Case(**c_data)
                session.add(case)
                await session.flush()
                
                # 4. Create Timeline for each case
                timeline = CaseTimeline(
                    case_id=case.id,
                    title="Main Case Timeline",
                    is_primary=True,
                    created_by=case.created_by
                )
                session.add(timeline)
                await session.flush()
                
                # 5. Create Events
                base_date = datetime.now(UTC) - timedelta(days=30)
                events = [
                    TimelineEvent(
                        timeline_id=timeline.id,
                        case_id=case.id,
                        title="Initial Consultation",
                        description="Met with client to discuss case merits.",
                        event_type=EventType.MEETING.value,
                        event_date=base_date,
                        created_by=case.created_by
                    ),
                    TimelineEvent(
                        timeline_id=timeline.id,
                        case_id=case.id,
                        title="Complaint Filed",
                        description="Formal filing with the court.",
                        event_type=EventType.FILING.value,
                        event_date=base_date + timedelta(days=7),
                        created_by=case.created_by
                    ),
                    TimelineEvent(
                        timeline_id=timeline.id,
                        case_id=case.id,
                        title="Discovery Phase Started",
                        description="Gathering relevant evidence and documents.",
                        event_type=EventType.DISCOVERY.value,
                        event_date=base_date + timedelta(days=14),
                        created_by=case.created_by
                    )
                ]
                session.add_all(events)
            
            await session.commit()
            print("Successfully seeded database.")
            
        except Exception as e:
            await session.rollback()
            print(f"Error seeding database: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(seed())
