#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from models import *
from apps.reporters.models import *


class NigeriaFormsLogic:
    ''' This class will hold the nigeria-specific forms logic.
        I'm not sure whether this will be the right structure
        this was just for getting something hooked up '''
       
    _form_lookups = {"nets" : {
                                "class" : NetDistribution, 
                                "netloc" : "location", 
                                "distributed" : "distributed", 
                                "expected" : "expected", 
                                "actual" : "actual",
                                "discrepancy" : "discrepancy", 
                                }, 
                     "net" : {    "class" : CardDistribution, 
                                  "couploc" : "location", 
                                  "settlements" : "settlements", 
                                  "people" : "people", 
                                  "netcards" : "distributed",
                                  }
                     }
        
    _foreign_key_lookups = {"Location" : "code" }

    def validate(self, *args, **kwargs):
        message = args[0]
        form_entry = args[1]
        if form_entry.form.type == "register":
            data = form_entry.to_dict()
            print "\n\n%r\n\n" % data
                
            # check that ALL FIELDS were provided
            required = ["location", "role", "password", "name"]
            missing = [t for t in required if data[t] is None]
            
            # in case we need help, build a valid reminder string
            help = ("%s register " % form_entry.domain.code.lower()) +\
                " ".join(["<%s>" % t for t in required])
                
            # missing fields! collate them, and
            # send back a friendly non-localized
            # error message, then abort
            if missing:
                mis_str = ", ".join(missing)
                return ["Missing fields: %s" % mis_str, help]
            
            try:
                # attempt to load the location and role objects
                # via their codes, which will raise if nothing
                # was found TODO: combine the exceptions
                data["location"] = Location.objects.get(code__iexact=data["location"])
                data["role"]     = Role.objects.get(code__iexact=data["role"])
            
            except Location.DoesNotExist:
                return ["Invalid location code: %s" %
                    data["location"], help]
            
            except Role.DoesNotExist:
                return ["Invalid role code: %s" %
                    data["role"], help]
            
            # parse the name via Reporter
            data["alias"], data["first_name"], data["last_name"] =\
                Reporter.parse_name(data.pop("name"))
            
            # check that the name/alias
            # hasn't already been registered
            reps = Reporter.objects.filter(alias=data["alias"])
            if len(reps):
                return ["Already been registed: %s" %
                    data["alias"], help]
            
            # all fields were present and correct, so copy them into the
            # form_entry, for "actions" to pick up again without re-fetching
            form_entry.rep_data = data
            
            # nothing went wrong. the data structure
            # is ready to spawn a Reporter object
            return None
        elif form_entry.form.type in self._form_lookups.keys() and not message.reporter:
            return [ "You must register your phone before submitting data" ]
        
    

    def actions(self, *args, **kwargs):
        message = args[0]
        form_entry = args[1]
        if form_entry.form.type == "register":
            rep = Reporter.objects.create(**form_entry.rep_data)
            message.respond("Reporter %s (#%d) added" % (rep.alias, rep.pk))
        elif self._form_lookups.has_key(form_entry.form.type):
            # this borrows a lot from supply.  I think we can make this a utility call
            to_use = self._form_lookups[form_entry.form.type]
            form_class = to_use["class"]
            instance = form_class()
            for token_entry in form_entry.tokenentry_set.all():
                if to_use.has_key(token_entry.token.abbreviation):
                    field_name = to_use[token_entry.token.abbreviation]
                    # this is sillyness.  this gets the model type from the metadata
                    # and if it's a foreign key then "rel" will be non null
                    foreign_key = instance._meta.get_field_by_name(field_name)[0].rel
                    if foreign_key:
                        # we can't just blindly set it, but we can get the class out 
                        fk_class = foreign_key.to
                        # and from there the name
                        fk_name = fk_class._meta.object_name
                        # and from there we look it up in our table
                        field = self._foreign_key_lookups[fk_name]
                        # get the object instance
                        filters = { field : token_entry.data }
                        try:
                            fk_instance = fk_class.objects.get(**filters)
                            setattr(instance, field_name, fk_instance)
                        except fk_class.DoesNotExist:
                            # ah well, we tried.  Is this a real error?  It might be, but if this
                            # was a required field then the save() will fail
                            pass
                    else:
                        setattr(instance, to_use[token_entry.token.abbreviation], token_entry.data)
            instance.reporter = message.reporter
            instance.save()
        