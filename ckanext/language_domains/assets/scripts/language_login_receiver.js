window.addEventListener('message', function(_event){

  const trusted_domains = TRUSTED_LANG_DOMAINS || [];

  if( ! Array.prototype.includes.call(trusted_domains, _event.origin) ){
    return;
  }

  if( ! _event.data.session_user || ! _event.data.session_token || ! _event.data.target_domain || ! _event.data.target_language ){
    return;
  }

  $.ajax({
    'url': '/user/language_domain_login',
    'type': 'POST',
    'dataType': 'JSON',
    'data': _event.data,
    'complete': function(_data){
      if( _data.responseJSON ){  // we have response JSON
        if( _data.responseJSON.success ){  // successful format guess
          console.log(_data.responseJSON);
        }else{  // validation error
          console.log(_data);
        }
      }else{  // fully flopped ajax request
        console.log(_data);
      }
    }
  });

});