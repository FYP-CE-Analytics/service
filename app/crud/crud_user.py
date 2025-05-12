from app.crud.base import CRUDBase
from motor.core import AgnosticDatabase
from app.models.user import UserModel
from app.schemas.user import UserCreate, UserUpdate
from fastapi import HTTPException
from app.services.ed_forum_service import EdService
from odmantic import ObjectId
from app.crud.crud_unit import unit
from typing import Dict, Any, List
from app.models.unit_dashboard import UnitStatus
from datetime import datetime


class CRUDUser(CRUDBase[UserModel, UserCreate, UserUpdate]):
    async def create(self, db: AgnosticDatabase, *, obj_in: UserCreate) -> UserModel:
        # lower case for email
        obj_in.email = obj_in.email.lower()
        user = {
            **obj_in.model_dump()
        }
        api_key = obj_in.api_key
        ed_service = EdService(api_key)
        try:
            active_courses = await ed_service.get_user_active_courses()
            user["available_units"] = [course.model_dump(exclude={'last_active'}) for course in active_courses]

            print(user)
        except Exception as e:
            print(f"Error with API key with error {str(e)}")

        return await self.engine.save(UserModel(**user))

    async def sync_user_units(self, db: AgnosticDatabase, user_id: str) -> UserModel:
        """
        Sync a user's units from Ed service to database.
        Updates unit statuses and maintains history.
        """
        try:
            # Get the user
            user = await self.get(db, {"id": ObjectId(user_id)})
            if not user:
                raise HTTPException(status_code=404, detail=f"User not found")

            # Create Ed service with user's API key
            ed_service = EdService(user.api_key)

            try:
                # Fetch current active courses from Ed
                current_courses = await ed_service.get_user_active_courses()
                current_course_ids = {course.id for course in current_courses}

                # Get all units associated with this user
                existing_units = await unit.get_multi(
                    db, 
                    {"id": {"$in": list(current_course_ids)}}
                )
                existing_unit_ids = {unit.id for unit in existing_units}

                # Update available units in user model
                user.available_units = [course.model_dump(exclude={'last_active'}) for course in current_courses]                    

                # Update user
                updated_user = await self.update(db, db_obj=user, obj_in=user)
                return updated_user

            except Exception as e:
                print(f"Error syncing units: {str(e)}")
                return user

        except Exception as e:
            print(f"Error syncing units: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error syncing units: {str(e)}")

    async def update_selected_units(self, db: AgnosticDatabase, user_id: str, selected_unit_ids: List[int]) -> UserModel:
        """
        Update user's selected units and update unit statuses accordingly
        """
        print("selected_unit_ids", selected_unit_ids)
        try:
            user = await self.get(db, {"id": ObjectId(user_id)})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            # Get current selected units
            current_selected = set(unit_info.id for unit_info in user.selected_units)
            new_selected = set(selected_unit_ids)

            # Units to be added
            to_add = new_selected - current_selected
            # Units to be removed
            to_remove = current_selected - new_selected

            updated_selected_units = [unit_info.model_dump() for unit_info in user.selected_units if unit_info.id not in to_remove]
            print("updated_selected_units", updated_selected_units)
            # if unit is not in the database, create it and set status to active otherwise update the status to active
            for unit_id in to_add:
                unit_obj = await unit.get(db, {"id": unit_id})
                print("unit_obj", unit_obj)
                if unit_obj:
                    ## convert the course info to the course info embeded model
                    updated_selected_units.append(unit_obj.model_dump())
                    # await unit.update(
                    #     db,
                    #     db_obj=unit_obj,
                    #     obj_in={"status": UnitStatus.ACTIVE}
                    # )
                else:
                    ## create needs  the full course info
                    ed_service = EdService(user.api_key)
                    course_info = await ed_service.get_course_info(unit_id)

                    # Convert datetime fields to ISO format strings
                    course_info.created_at = course_info.created_at.isoformat() if type(course_info.created_at) == datetime else course_info.created_at                    
                    # Create unit
                    await unit.create(
                        db,
                        obj_in=course_info
                    )
                    
                    # Convert to CourseInfoEmbededModel format
                    selected_unit = {
                        "id": course_info.id,
                        "name": course_info.name,
                        "code": course_info.code,
                        "year": str(course_info.year),
                        "session": course_info.session,
                        "status": course_info.status,
                        "created_at": course_info.created_at,
                    }
                    updated_selected_units.append(selected_unit)


            for unit_id in to_remove:
                unit_obj = await unit.get(db, {"id": unit_id})
                if unit_obj:
                    await unit.update(
                        db,
                        db_obj=unit_obj,
                        obj_in={"status": UnitStatus.PAST}
                    )

            user.selected_units = updated_selected_units
            print("user to be updated", user)
            return await self.engine.save(user)

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


user = CRUDUser(UserModel)
