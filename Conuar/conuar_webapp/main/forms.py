from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from .models import SystemConfiguration

User = get_user_model()

class LoginForm(forms.Form):
    """Form for user login"""
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingresa tu nombre de usuario',
            'required': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingresa tu contraseña',
            'required': True
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        
        if not username or not password:
            raise forms.ValidationError('Tanto el nombre de usuario como la contraseña son requeridos.')
        
        return cleaned_data

class SystemConfigurationForm(forms.ModelForm):
    """Form for system configuration settings"""
    
    class Meta:
        model = SystemConfiguration
        fields = [
            'media_storage_path',
            'camera_1_ip',
            'camera_2_ip', 
            'camera_3_ip',
            'plc_ip',
            'plc_port'
        ]
        widgets = {
            'media_storage_path': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: /path/to/media/folder/'
            }),
            'camera_1_ip': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '192.168.1.100'
            }),
            'camera_2_ip': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '192.168.1.101'
            }),
            'camera_3_ip': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '192.168.1.102'
            }),
            'plc_ip': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '192.168.1.50'
            }),
            'plc_port': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '502',
                'min': '1',
                'max': '65535'
            })
        }
        labels = {
            'media_storage_path': 'Ruta de Almacenamiento de Medios',
            'camera_1_ip': 'IP Cámara 1',
            'camera_2_ip': 'IP Cámara 2',
            'camera_3_ip': 'IP Cámara 3',
            'plc_ip': 'IP del PLC',
            'plc_port': 'Puerto del PLC'
        }
        help_texts = {
            'media_storage_path': 'Ruta donde se almacenan las fotos de inspección',
            'camera_1_ip': 'Dirección IP de la primera cámara',
            'camera_2_ip': 'Dirección IP de la segunda cámara',
            'camera_3_ip': 'Dirección IP de la tercera cámara',
            'plc_ip': 'Dirección IP del PLC que controla la máquina',
            'plc_port': 'Puerto de comunicación con el PLC (por defecto 502)'
        }

class CustomUserCreationForm(UserCreationForm):
    """Custom user creation form with additional fields"""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'correo@ejemplo.com'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Apellido'
        })
    )
    is_inspector = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    is_supervisor = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'is_inspector', 'is_supervisor')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de usuario'
            }),
        }
        labels = {
            'username': 'Nombre de Usuario',
            'email': 'Correo Electrónico',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'password1': 'Contraseña',
            'password2': 'Confirmar Contraseña',
            'is_inspector': 'Es Inspector',
            'is_supervisor': 'Es Supervisor'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Contraseña'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirmar contraseña'
        })
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_inspector = self.cleaned_data.get('is_inspector', False)
        user.is_supervisor = self.cleaned_data.get('is_supervisor', False)
        if commit:
            user.save()
        return user

class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with Bootstrap styling"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Contraseña actual'
        })
        self.fields['new_password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Nueva contraseña'
        })
        self.fields['new_password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirmar nueva contraseña'
        })
        
        self.fields['old_password'].label = 'Contraseña Actual'
        self.fields['new_password1'].label = 'Nueva Contraseña'
        self.fields['new_password2'].label = 'Confirmar Nueva Contraseña'
