import math

from account.models import Branch


class BranchAssignmentService:
    @staticmethod
    def calculate_haversine_distance(lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points
        on the earth (specified in decimal degrees) using Haversine formula in kilometers.
        """
        R = 6371.0  # Radius of earth in kilometers

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        return distance

    @classmethod
    def get_nearest_active_branch(cls, latitude, longitude):
        """
        Finds the nearest active branch to the given customer coordinates.
        Returns the Branch instance or None if no active branches exist.
        """
        active_branches = Branch.objects.all().only(
            "id", "name", "address", "latitude", "longitude"
        )

        if not active_branches.exists():
            return None

        # If only 1 branch exists, return it directly
        if active_branches.count() == 1:
            return active_branches.first()

        # Find branch with minimum Haversine distance
        nearest_branch = min(
            active_branches,
            key=lambda b: cls.calculate_haversine_distance(
                latitude, longitude, b.latitude, b.longitude
            ),
        )
        return nearest_branch
