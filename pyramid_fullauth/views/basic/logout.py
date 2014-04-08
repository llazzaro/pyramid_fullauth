# Copyright (c) 2013 - 2014 by pyramid_fullauth authors and contributors <see AUTHORS file>
#
# This module is part of pyramid_fullauth and is released under
# the MIT License (MIT): http://opensource.org/licenses/MIT
"""De-authentication related view."""

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound
from pyramid.security import forget
from pyramid.security import NO_PERMISSION_REQUIRED

from pyramid_fullauth.views import BaseView


@view_config(route_name='logout', permission=NO_PERMISSION_REQUIRED)
class LogoutView(BaseView):

    """Logout view."""

    def __call__(self):
        """Logout action."""
        location = '/'
        if self.config.redirects.logout:
            location = self.request.route_path(self.config.redirects.logout)

        return HTTPFound(location=location, headers=forget(self.request))