from django import forms
from .audit import record


class AnimalDeleteForm(forms.Form):
    confirm = forms.BooleanField(label='I understand that this animal record, submissions, history and attached photos will be permanently deleted.')
    password = forms.CharField(label='Your current password', strip=False, widget=forms.PasswordInput(attrs={'autocomplete':'current-password'}))

    def __init__(self, *args, user, animal, **kwargs):
        self.user, self.animal = user, animal
        super().__init__(*args, **kwargs)

    def clean_password(self):
        value = self.cleaned_data['password']
        if not self.user.check_password(value):
            record('access', 'animal.delete_confirmation_failed', actor=self.user, target=self.animal, animal_id=self.animal.pk, outcome='failure')
            raise forms.ValidationError('Your password is incorrect.')
        return value
