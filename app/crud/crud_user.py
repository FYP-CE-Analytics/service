from app.crud.base import CRUDBase
from motor.core import AgnosticDatabase
from app.models.user import UserModel, UnitInfoModel
from app.schemas.user import UserCreate, UserUpdate
from fastapi import HTTPException
from app.services.ed_forum_service import EdService
from odmantic import ObjectId
from app.crud.crud_unit import unit
from typing import Dict, Any


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

            user["available_units"] = [UnitInfoModel(
                **course.model_dump()) for course in active_courses]
        except Exception as e:
            print(f"Error with API key with error {str(e)}")

        return await self.engine.save(UserModel(**user))

    async def get_user_synced(self, db: AgnosticDatabase, email: str) -> UserModel:
        """
        Sync a user's units from Ed service to database.

        Args:
            db: Database connection
            user_id: ID of the user to sync units for

        Returns:
            Dictionary with sync results
        """
        try:
            # Get the user ignore case
            user = await self.get(db, {"email": email.lower()})
            if not user:
                raise HTTPException(
                    status_code=404, detail=f"User with ID {email} not found")
            # Create Ed service with user's API key
            ed_service = EdService(user.api_key)

            try:
                # Fetch current active courses from Ed
                current_courses = await ed_service.get_user_active_courses()
                user_res = await self.update(
                    db, db_obj=user, obj_in={"available_units": [UnitInfoModel(
                        **course.model_dump()) for course in current_courses]}
                )
                new_units = []
                # Sync units to the units collection
                for course in current_courses:
                    # Check if unit exists in database
                    existing_unit = await unit.get(db, {"id": course.id})
                    if not existing_unit:
                        new_units.append(course)
                        # Create the unit in the database
                        unit_create = UnitInfoModel(
                            **course.model_dump())
                        await unit.create(db, obj_in=unit_create)
                print({
                    "success": True,
                    "inserted_unit": len(new_units),
                })
            except Exception as e:
                print(f"Error syncing units: {str(e)}")
                return user
                # might need to hadle this
                # raise HTTPException(
                #     status_code=401, detail=f"Please check your API key: {str(e)}")

            return user_res

        except Exception as e:
            print(f"Error syncing units: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error syncing units: {str(e)}")


user = CRUDUser(UserModel)
