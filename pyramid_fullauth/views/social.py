# -*- coding: utf-8 -*-

# Copyright (c) 2013 by pyramid_fullauth authors and contributors <see AUTHORS file>
#
# This module is part of pyramid_fullauth and is released under
# the MIT License (MIT): http://opensource.org/licenses/MIT

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound
from pyramid.security import NO_PERMISSION_REQUIRED

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError

from pyramid_basemodel import Session
from pyramid_fullauth.views import BaseView
from pyramid_fullauth.models import User
from pyramid_fullauth.models import AuthenticationProvider
from pyramid_fullauth.events import BeforeSocialRegister
from pyramid_fullauth.events import AfterSocialRegister
from pyramid_fullauth.events import AfterSocialLogIn
from pyramid_fullauth.events import SocialAccountAlreadyConnected
from pyramid_fullauth import tools


@view_config(context='velruse.AuthenticationComplete',
             permission=NO_PERMISSION_REQUIRED,
             renderer="pyramid_fullauth:resources/templates/register.mako")
class SocialLoginViews(BaseView):

    '''
        Social login views definition
    '''

    def set_provider(self, user, provider_name, user_provider_id):
        '''
            Method sets the provider authentication method for user.
        '''
        if user.id:
            try:
                provider_auth = Session.query(
                    AuthenticationProvider
                ).filter(
                    AuthenticationProvider.user_id == user.id,
                    AuthenticationProvider.provider == provider_name
                ).one()
                if provider_auth.provider_id != user_provider_id:
                    return False
                return True
            except NoResultFound:
                pass

        provider_auth = AuthenticationProvider(
            provider=provider_name,
            provider_id=user_provider_id
        )
        user.providers.append(provider_auth)
        Session.flush()
        return True

    def __call__(self):
        """
        Action provides social authorization functionality.

        When authorization with facebook or twitter is done successfully
        action tries to find existing user in database,
        if it exists - login this user, otherwise creates new user.
        """

        context = self.request.context
        response_values = {
            'status': False,
            'csrf_token': self.request.session.get_csrf_token()
        }
        user = self.request.user

        if user:
            # Lets try to connect our user
            response = self._connect_user(response_values)
            if response:
                return response
        else:
            try:
                user = Session.query(
                    User
                ).join(AuthenticationProvider).filter(
                    AuthenticationProvider.provider == context.provider_name,
                    AuthenticationProvider.provider_id == context.profile['accounts'][0]['userid']
                ).one()
            except NoResultFound:
                user = None

            # If the user for the provider was not found then check if in the DB exists user with the same email
            if not user:
                user = self._register_user()
                try:
                    self.request.registry.notify(
                        AfterSocialRegister(
                            self.request, user, context.profile, response_values))
                except HTTPFound as redirect:
                    # it's a redirect, let's follow it!
                    return redirect

        # if we're here, user exists
        try:
            self.request.registry.notify(AfterSocialLogIn(self.request, user, context.profile))
        except HTTPFound as redirect:
            # it's a redirect, let's follow it!
            return self.request.login_perform(user, location=redirect.location)
        else:
            return self.request.login_perform(user)

    def _connect_user(self, response_values):
        """
        Connect user to social account.

        :param dict response_values:

        :returns: either response values if any error occured,
            or HTTPFound if raised in SocialAccountAlreadyConnected

        """
        context = self.request.context
        user = self.request.user
        try:
            if not self.set_provider(
                user, context.provider_name, context.profile['accounts'][0]['userid']
            ):
                response_values['msg'] = 'Your account is already connected to other {provider} account.'.format(
                    provider=context.provider_name)
                return response_values
        except IntegrityError:
            response_values['msg'] = 'This {provider} account is already connected with other account.'.format(
                provider=context.provider_name
            )
            try:
                self.request.registry.notify(
                    SocialAccountAlreadyConnected(
                        self.request, user, context.profile, response_values))
            except HTTPFound as redirect:
                # it's a redirect, let's follow it!
                return redirect
            return response_values

    def _register_user(self):
        """Actually register new user in the system based on context values."""
        context = self.request.context
        email = self._email_from_context()

        try:
            user = Session.query(User).filter(User.email == email).one()
            # If we are here that means that in the DB exists user with the same email but without the provider
            # then we connect social account to this user
            self.set_provider(user, context.provider_name, context.profile['accounts'][0]['userid'])
            Session.flush()
        except NoResultFound:
            length_min = self.config.register.password.length_min
            user = User(
                email=email,
                password=tools.password_generator(length_min),
                address_ip=self.request.remote_addr
            )
            self.request.registry.notify(BeforeSocialRegister(self.request, user, context.profile))
            self.set_provider(user, context.provider_name, context.profile['accounts'][0]['userid'])
            Session.add(user)
            Session.flush()
            user.is_active = True
        return user

    def _email_from_context(self):
        """Extract or generate email from context values."""
        context = self.request.context
        # getting verified email from provider
        if 'verifiedEmail' in context.profile:
            return context.profile['verifiedEmail']
        # getting first of the emails provided by social login provider
        elif 'emails' in context.profile and context.profile['emails'] and 'value' in context.profile['emails'][0]:
            return context.profile['emails'][0]['value']
        # generating some random email address based on social userid and provider domain
        else:
            return u'{0}@{1}'.format(
                context.profile['accounts'][0]['userid'],
                context.profile['accounts'][0]['domain']
            )
